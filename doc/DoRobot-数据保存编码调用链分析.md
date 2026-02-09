# DoRobot-before 数据保存和编码调用链分析

> 分析运行 `bash scripts/run_so101.sh` 时的数据保存和编码流程

---

## 📋 完整调用链

### 1️⃣ 启动脚本

**文件**: `scripts/run_so101.sh`

- **第 625 行**: 启动主程序

```bash
python "$PROJECT_ROOT/operating_platform/core/main.py" \
    --robot.type=so101 \
    --record.repo_id="$repo_id" \
    --record.single_task="$single_task"
```

### 2️⃣ 主程序入口

**文件**: `operating_platform/core/main.py`

**关键代码**:

- **第 40 行**: 导入 Record 类

```python
from operating_platform.core.record import Record, RecordConfig
```

- **第 439-445 行**: 创建 Record 实例

```python
record = Record(
    fps=cfg.record.fps,
    robot=daemon.robot,
    daemon=daemon,
    record_cfg=record_cfg,
    record_cmd=record_cmd
)
```

- **第 464 行**: 开始录制

```python
record.start()
```

- **第 524 行**: 保存 episode（用户按 's' 键时）

```python
metadata = record.save()
```

### 3️⃣ Record 类 - 录制控制层

**文件**: `operating_platform/core/record.py`

#### 3.1 初始化 (第 107-195 行)

```python
class Record:
    def __init__(self, fps, robot, daemon, record_cfg, record_cmd):
        # 创建 DoRobotDataset 实例
        self.dataset = DoRobotDataset.create(
            record_cfg.repo_id,
            record_cfg.fps,
            root=record_cfg.root,
            robot=robot,
            features=dataset_features,
            use_videos=record_cfg.video,
            use_audios=len(robot.microphones) > 0,
            image_writer_processes=record_cfg.num_image_writer_processes,
            image_writer_threads=record_cfg.num_image_writer_threads_per_camera * len(robot.cameras),
        )

        # 初始化异步保存器
        if self.use_async_save:
            self.async_saver = AsyncEpisodeSaver(
                max_workers=record_cfg.num_async_save_workers
            )
```

#### 3.2 数据采集循环 (第 224-250 行)

```python
def process(self):
    while self.running:
        # 获取观测和动作数据
        observation = self.daemon.get_observation()
        action = self.daemon.get_obs_action()

        # 构建数据帧
        observation_frame = build_dataset_frame(self.dataset.features, observation, prefix="observation")
        action_frame = build_dataset_frame(self.dataset.features, action, prefix="action")
        frame = {**observation_frame, **action_frame}

        # 添加到 episode buffer
        with self._buffer_lock:
            self.dataset.add_frame(frame, self.record_cfg.single_task)
```

#### 3.3 保存入口 (第 358-374 行)

```python
def save(self, skip_encoding: bool | None = None) -> EpisodeMetadata | dict:
    """保存 episode - 默认异步，需要时回退到同步"""
    if skip_encoding is None:
        skip_encoding = self.skip_encoding

    if self.use_async_save:
        return self.save_async(skip_encoding=skip_encoding)
    else:
        return self.save_sync(skip_encoding=skip_encoding)
```

#### 3.4 同步保存 (第 313-356 行)

```python
def save_sync(self, skip_encoding: bool = False) -> dict:
    """同步保存方法"""
    # 调用 DoRobotDataset.save_episode
    episode_index = self.dataset.save_episode(skip_encoding=skip_encoding)

    # 更新元数据文件
    update_dataid_json(self.record_cfg.root, episode_index, self.record_cmd)

    # 推送到 Hub（如果配置）
    if self.record_cfg.push_to_hub:
        self.dataset.push_to_hub(tags=self.record_cfg.tags, private=self.record_cfg.private)

    return data
```

#### 3.5 异步保存 (第 271-311 行)

```python
def save_async(self, skip_encoding: bool = False) -> EpisodeMetadata:
    """异步保存 - 立即返回，后台处理"""
    import copy

    # 在锁内原子性地捕获 buffer 并切换到新 buffer
    with self._buffer_lock:
        # 深拷贝当前 buffer
        buffer_copy = copy.deepcopy(self.dataset.episode_buffer)
        # 创建新的 episode buffer
        self.dataset.episode_buffer = self._create_new_episode_buffer()

    # 将保存任务加入队列（在锁外，最小化锁持有时间）
    metadata = self.async_saver.queue_save(
        episode_buffer=buffer_copy,
        dataset=self.dataset,
        record_cfg=self.record_cfg,
        record_cmd=self.record_cmd,
        skip_encoding=skip_encoding,
    )

    return metadata
```

### 4️⃣ AsyncEpisodeSaver - 异步保存管理器

**文件**: `operating_platform/core/async_episode_saver.py`

#### 4.1 队列保存任务 (第 180-230 行)

```python
def queue_save(self, episode_buffer, dataset, record_cfg, record_cmd, skip_encoding=False):
    """将 episode 加入保存队列"""
    # 预分配 episode index
    episode_index = self.allocate_next_index()

    # 创建保存任务
    task = SaveTask(
        episode_index=episode_index,
        episode_buffer=episode_buffer,
        dataset=dataset,
        record_cfg=record_cfg,
        record_cmd=record_cmd,
        skip_encoding=skip_encoding,
    )

    # 加入队列
    self.save_queue.put(task)

    return EpisodeMetadata(episode_index=episode_index, queue_position=queue_pos)
```

#### 4.2 后台保存线程 (第 250-380 行)

```python
def _save_worker(self):
    """后台工作线程 - 处理保存队列"""
    while self._running or not self.save_queue.empty():
        try:
            task = self.save_queue.get(timeout=1.0)
            self._execute_save(task)
        except queue.Empty:
            continue

def _execute_save(self, task):
    """执行保存任务"""
    ep_idx = task.episode_index

    # 调用 DoRobotDataset.save_episode
    task.dataset.save_episode(
        episode_data=task.episode_buffer,
        skip_encoding=task.skip_encoding
    )

    # 更新元数据
    update_dataid_json(task.record_cfg.root, ep_idx, task.record_cmd)
```

### 5️⃣ DoRobotDataset - 数据集核心层

**文件**: `operating_platform/dataset/dorobot_dataset.py`

#### 5.1 添加帧到 buffer (第 899-950 行)

```python
def add_frame(self, frame: dict, task: str | None = None) -> None:
    """将帧添加到 episode buffer（内存中）"""
    # 验证帧数据
    validate_frame(frame, self.features)

    # 自动添加 frame_index 和 timestamp
    frame_index = self.episode_buffer["size"]
    timestamp = frame_index / self.fps

    # 添加到 buffer
    for key in self.features:
        if key in frame:
            self.episode_buffer[key].append(frame[key])

    self.episode_buffer["size"] += 1
    self.episode_buffer["timestamp"].append(timestamp)
    self.episode_buffer["task"].append(task)
```

#### 5.2 保存 episode (第 955-1050 行)

```python
def save_episode(self, episode_data: dict | None = None, skip_encoding: bool = False) -> int:
    """保存 episode 到磁盘"""
    # 1. 验证 episode buffer
    validate_episode_buffer(episode_buffer, self.meta.total_episodes, self.features)

    # 2. 处理 buffer 数据
    episode_length = episode_buffer.pop("size")
    tasks = episode_buffer.pop("task")
    episode_index = episode_buffer["episode_index"]

    # 3. 添加索引和任务信息
    episode_buffer["index"] = np.arange(self.meta.total_frames, self.meta.total_frames + episode_length)
    episode_buffer["episode_index"] = np.full((episode_length,), episode_index)
    episode_buffer["task_index"] = np.array([self.meta.get_task_index(task) for task in tasks])

    # 4. 转换列表为 numpy 数组
    for key, ft in self.features.items():
        if key not in ["index", "episode_index", "task_index"] and ft["dtype"] not in ["image", "video", "audio"]:
            episode_buffer[key] = np.stack(episode_buffer[key])

    # 5. 等待图像写入完成
    self._wait_episode_images(episode_index, episode_length)

    # 6. 保存 Parquet 表格数据
    self._save_episode_table(episode_buffer, episode_index)

    # 7. 编码视频（如果不跳过）
    if len(self.meta.video_keys) > 0 and not skip_encoding:
        video_paths = self.encode_episode_videos(episode_index)
    elif skip_encoding:
        logging.info(f"Skipping video encoding for episode {episode_index} (cloud offload mode)")

    # 8. 保存元数据
    ep_stats = compute_episode_stats(episode_buffer, self.features)
    self.meta.save_episode(episode_index, episode_length, episode_tasks, ep_stats, skip_encoding=skip_encoding)

    return episode_index
```

#### 5.3 保存 Parquet 表格 (第 1108-1150 行)

```python
def _save_episode_table(self, episode_buffer: dict, episode_index: int) -> None:
    """保存 episode 数据为 Parquet 文件"""
    # 创建 HuggingFace Dataset
    episode_dict = {key: episode_buffer[key] for key in self.hf_features}
    ep_dataset = datasets.Dataset.from_dict(episode_dict, features=self.hf_features, split="train")

    # 保存为 Parquet
    ep_path = self.root / f"data/chunk-{episode_index:03d}/episode_{episode_index:06d}.parquet"
    ep_path.parent.mkdir(parents=True, exist_ok=True)
    ep_dataset.to_parquet(str(ep_path))
```

#### 5.4 编码视频 (第 1281-1312 行)

```python
def encode_episode_videos(self, episode_index: int) -> dict:
    """使用 ffmpeg 将 PNG 帧编码为 MP4 视频"""
    video_paths = {}

    for key in self.meta.video_keys:
        # 图像目录路径
        img_dir = self.root / f"videos/{key}/episode_{episode_index:06d}"

        # 视频输出路径
        video_path = self.root / f"videos/{key}/episode_{episode_index:06d}.mp4"

        # 调用 ffmpeg 编码
        encode_video_frames(img_dir, video_path, self.fps, overwrite=True)

        video_paths[key] = str(video_path)

    return video_paths
```

### 6️⃣ 视频编码工具

**文件**: `operating_platform/utils/video.py`

```python
def encode_video_frames(img_dir, video_path, fps, overwrite=True):
    """使用 ffmpeg 编码视频"""
    # 构建 ffmpeg 命令
    cmd = [
        "ffmpeg",
        "-f", "image2",
        "-r", str(fps),
        "-i", f"{img_dir}/frame_%06d.png",
        "-vcodec", "libx264",
        "-pix_fmt", "yuv420p",
        "-y" if overwrite else "-n",
        str(video_path)
    ]

    # 执行编码
    subprocess.run(cmd, check=True)
```

---

## 🔄 数据流程图

```
用户按 's' 键
    ↓
main.py: record.save()
    ↓
record.py: save() → save_async() / save_sync()
    ↓
    ├─ 同步模式 (save_sync)
    │   ↓
    │   dataset.save_episode(skip_encoding=False)
    │       ↓
    │       dorobot_dataset.py: save_episode()
    │           ├─ 1. 验证 buffer
    │           ├─ 2. 处理数据
    │           ├─ 3. 等待图像写入
    │           ├─ 4. _save_episode_table() → Parquet 文件
    │           ├─ 5. encode_episode_videos() → MP4 视频
    │           └─ 6. meta.save_episode() → 元数据
    │
    └─ 异步模式 (save_async)
        ↓
        1. 深拷贝 episode_buffer
        2. 创建新 buffer
        3. async_saver.queue_save()
            ↓
            async_episode_saver.py: _save_worker()
                ↓
                dataset.save_episode(episode_data=buffer_copy)
                    ↓
                    （同上述同步流程）
```

---

## 📁 关键文件总结

| 文件                          | 作用         | 关键方法                                                                            |
| ----------------------------- | ------------ | ----------------------------------------------------------------------------------- |
| `scripts/run_so101.sh`        | 启动脚本     | 启动 main.py                                                                        |
| `core/main.py`                | 主程序入口   | 创建 Record，处理用户输入                                                           |
| `core/record.py`              | 录制控制层   | `save()`, `save_async()`, `save_sync()`, `process()`                                |
| `core/async_episode_saver.py` | 异步保存管理 | `queue_save()`, `_save_worker()`, `_execute_save()`                                 |
| `dataset/dorobot_dataset.py`  | 数据集核心   | `add_frame()`, `save_episode()`, `_save_episode_table()`, `encode_episode_videos()` |
| `utils/video.py`              | 视频编码工具 | `encode_video_frames()`                                                             |
| `utils/dataset.py`            | 数据集工具   | `build_dataset_frame()`, `hw_to_dataset_features()`                                 |

---

## 🎯 数据保存格式

### Parquet 文件

**位置**: `data/chunk-{episode_idx:03d}/episode_{episode_idx:06d}.parquet`

**内容**:

- `index`: 全局帧索引
- `episode_index`: episode 索引
- `timestamp`: 时间戳
- `task_index`: 任务索引
- `observation.*`: 观测数据（关节位置、图像路径等）
- `action.*`: 动作数据（目标关节位置等）

### 视频文件

**位置**: `videos/{camera_name}/episode_{episode_idx:06d}.mp4`

**编码参数**:

- 编码器: libx264
- 像素格式: yuv420p
- 帧率: 30 FPS（可配置）

### 元数据文件

**位置**: `meta_data/info.json`

**内容**:

- 数据集版本
- 机器人类型
- FPS
- 总 episodes 数
- 总帧数
- 任务列表
- 每个 episode 的统计信息

---

## ⚙️ 编码模式

### 1. 本地编码模式 (CLOUD=0)

- `skip_encoding=False`
- 本地编码视频
- 不上传

### 2. 云端原始模式 (CLOUD=1)

- `skip_encoding=True`
- 保存原始 PNG
- 上传到云端编码

### 3. 边缘服务器模式 (CLOUD=2)

- `skip_encoding=True`
- 保存原始 PNG
- rsync 到边缘服务器

### 4. 云端编码模式 (CLOUD=3)

- `skip_encoding=False`
- 本地编码视频
- 上传编码后的视频

### 4. 本地原始模式 (CLOUD=4)

- `skip_encoding=True`
- 保存原始 PNG
- 不编码，不上传

---

## 🔍 关键技术点

### 1. 异步保存机制

- 使用 `AsyncEpisodeSaver` 管理后台保存队列
- 深拷贝 episode buffer 避免数据竞争
- 使用锁保护 buffer 切换操作
- 支持重试机制（最多 3 次）

### 2. 图像写入

- 使用多进程/多线程并行写入 PNG
- 每个相机独立的写入队列
- 等待机制确保图像写入完成后再编码

### 3. 视频编码

- 使用 ffmpeg 的 libx264 编码器
- 支持跳过编码（云端模式）
- 编码完成后删除原始 PNG（可选）

### 4. 数据验证

- 帧数据验证（特征匹配）
- Episode buffer 验证（完整性检查）
- 时间戳同步检查

---

**文档创建时间**: 2026-02-09
**分析版本**: DoRobot-before (v0.2.99)
