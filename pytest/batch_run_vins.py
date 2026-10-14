import argparse
from pathlib import Path
import sys
from typing import List, Dict, Any, Optional
import time
import subprocess
import re
import os
import shutil
from collections import Counter
import json
import signal

# _ROS_TIME_RE = re.compile(r"\[INFO\]\s*\[(\d+\.\d+)\]")
_ROS_TIME_RE = re.compile(r"\[(\d+\.\d+)\]")
# ============================================================
# 工具
# ============================================================
def find_file(directory: Path, key: str) -> List[Path]:
    return [p.resolve() for p in directory.rglob(key) if p.is_file()]

def update_config_output_path(config_path: Path, output_path: Path) -> None:
    """把 config 文件中的 output_path 改成指定路径（原地修改，带备份）。"""
    config_path = Path(config_path).resolve()
    if not config_path.exists():
        raise FileNotFoundError(f"config 文件不存在: {config_path}")

    text = config_path.read_text(encoding="utf-8")
    # 匹配形如:  output_path: "...."
    pattern = re.compile(r'^(\s*output_path\s*:\s*)".*?"', re.MULTILINE)
    if not pattern.search(text):
        raise RuntimeError(f"在 {config_path} 中未找到 output_path 字段")
    new_line = rf'\1"{output_path}"'
    new_text = pattern.sub(new_line, text)
    if new_text == text:
        print(f"output_path 已经是 {output_path}，无需修改")
        return
    # 备份一次原文件（只在第一次备份，避免覆盖）
    backup = config_path.with_suffix(config_path.suffix + ".bak")
    if not backup.exists():
        backup.write_text(text, encoding="utf-8")
    config_path.write_text(new_text, encoding="utf-8")
    print("***")
    print(f"已更新 config output_path -> {output_path}")
    # print("***")


class Harness:
    def __init__(self, workspace: str):
        self.workspace = workspace
        self.rviz_process: Optional[subprocess.Popen] = None
        self.vins_process: Optional[subprocess.Popen] = None
        self.bag_play_process: Optional[subprocess.Popen] = None
        self._vins_log_fh = None
        self.vins_log_path = None

    # ---------- bag ----------
    def get_bag_duration_seconds(self, bag: str) -> Optional[float]:
        result = subprocess.run(
            ["bash", "-lc",
             f"source {self.workspace}/install/setup.bash && "
             f"ros2 bag info {bag}"],
            capture_output=True, text=True, cwd=str(self.workspace))
        if result.returncode != 0:
            print("Failed to query bag duration via `ros2 bag info`")
            return None
        match = re.search(r"Duration:\s+([0-9.]+)s", result.stdout)
        if not match:
            print("Could not parse bag duration from `ros2 bag info` output")
            return None
        return float(match.group(1))

    # ---------- 进程 ----------
    def start_process(self, cmd: List[str]) -> subprocess.Popen:
        return subprocess.Popen(
            cmd, 
            stdout=subprocess.DEVNULL, 
            stderr=subprocess.STDOUT,
            text=True, cwd=str(self.workspace), start_new_session=True)

    def stop_process_group(self, process, name, timeout=5.0):
        if not process:
            return
        print(f"Stopping {name}...")
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            return
        try:
            process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            print(f"{name} did not stop after {timeout}s; killing it")
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            process.wait()

    def start_rviz(self):
        cmd = ["bash", "-c",
               f"source {self.workspace}/install/setup.bash && "
               f"ros2 launch vins vins_rviz.launch.xml"]
        print("Launching rviz")
        self.rviz_process = self.start_process(cmd)
        time.sleep(2)

    def start_vins(self, config: str):
        self._vins_log_fh = open(self.vins_log_path, 'w', encoding='utf-8')

        # cmd = ["bash", "-c",
        #        f"source {self.workspace}/install/setup.bash && "
        #        f"ros2 launch vins euroc.launch.py config_path:={config}"]
        cmd = ["bash", "-c",
           f"source {self.workspace}/install/setup.bash && "
           f"export PYTHONUNBUFFERED=1 && "
           f"ros2 launch vins euroc.launch.py config_path:={config}"]
        print("***")
        print("Launching vins")
        # print("***")
        # self.vins_process = self.start_process(cmd)
        self.vins_process = subprocess.Popen(
            cmd,
            stdout=self._vins_log_fh,
            stderr=subprocess.STDOUT,
            text=True,
            cwd=str(self.workspace),
            start_new_session=True,
        )
        time.sleep(2)
        if self.vins_process.poll() is not None:
            out, _ = self.vins_process.communicate(timeout=5)
            # raise RuntimeError(
            #     f"Launch failed (rc={self.vins_process.returncode}).\n"
            #     f"cmd: {' '.join(cmd)}\n---- output ----\n{out}")
            raise RuntimeError(f"Launch failed rc={self.vins_process.returncode}")

    def play_bag(self, bag: str) -> int:
        playback_duration = max(1, int(self.get_bag_duration_seconds(bag)))
        cmd = ["bash", "-c",
               (f"ros2 bag play {bag} "
                f"--playback-duration {playback_duration} --clock")]
        print("***")
        print(f"Playing bag: {bag} (playback_duration={playback_duration}s)")
        self.bag_play_process = self.start_process(cmd)
        time.sleep(2)
        if self.bag_play_process.poll() is not None:
            raise RuntimeError(
                f"bag play exited early rc={self.bag_play_process.returncode}, "
                f"cmd={' '.join(cmd)}")
        return playback_duration

    def stop_bag_play(self):
        self.stop_process_group(self.bag_play_process, "bag playback")
        self.bag_play_process = None

    def stop_vins(self):
        self.stop_process_group(self.vins_process, "ROS2 launch")
        self.vins_process = None

    def stop_rviz(self):
        self.stop_process_group(self.rviz_process, "rviz2")
        self.rviz_process = None

    def stop_all_processes(self):
        self.stop_bag_play(); time.sleep(2)
        self.stop_vins();     time.sleep(2)
        self.stop_rviz()

    def wait_for_bag_completion(self, timeout: float) -> bool:
        if not self.bag_play_process:
            return False
        try:
            self.bag_play_process.wait(timeout=timeout)
            ok = self.bag_play_process.returncode == 0
            self.bag_play_process = None
            return ok
        except subprocess.TimeoutExpired:
            print(f"Bag playback exceeded hard timeout {timeout}s, killing")
            self.stop_bag_play()
            return False


    def _scan_log(self, markers, case_sensitive: bool = False) -> dict:
        """
        markers: dict[name -> str]  例如 {"init": "Initialization finish!",
                                        "warn": "[WARN]"}
        返回: {name: 出现次数(按行计)}
        """
        result = {name: 0 for name in markers}
        if not getattr(self, "vins_log_path", None) or not self.vins_log_path.exists():
            return result

        needles = {
            name: (pat if case_sensitive else pat.lower())
            for name, pat in markers.items()
        }
        with self.vins_log_path.open("r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                hay = line if case_sensitive else line.lower()
                for name, needle in needles.items():
                    if needle in hay:
                        result[name] += 1
        print(f"[scan] {result}")
        return result

    def _time_to_marker(self, marker: str = "Initialization finish!"):
        """
        返回日志里首次出现 marker 时 ROS 时间戳(秒)，找不到返回 None。
        """
        if not getattr(self, "vins_log_path", None) or not self.vins_log_path.exists():
            return None
        marker_l = marker.lower()
        with self.vins_log_path.open("r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                if marker_l in line.lower():
                    m = _ROS_TIME_RE.search(line)
                    if m:
                        return float(m.group(1))
                    # 行里有 marker 但没时间戳
                    return None
        return None

    def _read_manifest_metrics(self, bag_path: Path) -> Dict[str, Any]:
        out: Dict[str, Any] = {
            "manifest_path": None,
            "total_yaw_deg": None,
            "a": None,
            "yaw_rate_radps": None,
        }
        manifest_path = bag_path.parent / "artifact_manifest.json"
        if not manifest_path.exists():
            print(f"  [manifest] 未找到 {manifest_path}")
            return out

        out["manifest_path"] = str(manifest_path)
        try:
            data = json.loads(manifest_path.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"  [manifest] 解析失败: {e}")
            return out

        phases = (
            data.get("trajectory", {})
                .get("execution", {})
                # .get("phase_timeline", [])
                .get("resolved", {})
                .get("cycle", [])
        )

        for ph in phases:
            # dur = ph.get("actual_duration_sec") or 0.0
            ptype = ph.get("type")

            if ptype == "path_follow":
                ramp = ph.get("accel_ramp_sec") or 0.0
                speed_mps = ph.get("speed_mps") or 0.0
                if ramp > 0 and speed_mps > 0:
                    out["a"] = float(speed_mps) / float(ramp)
                else:
                    out["a"] = 0.0
            elif ptype == "yaw_spin":
                total_yaw_deg = ph.get("total_yaw_deg") or 0.0
                yaw_rate_radps = ph.get("yaw_rate_radps") or 0.0
                out["total_yaw_deg"] = total_yaw_deg
                out["yaw_rate_radps"] = yaw_rate_radps

        return out


    def run(self, output:Path, config:str, bag:str, rviz:bool=False):
        self.vins_log_path = output / 'vins_run.log'
        output.mkdir(parents=True, exist_ok=True)
        # print("***")
        # print(f"output : {self.vins_log_path}")
        # print("***")

        result: Dict[str, Any] = {
            "bag": str(bag),
            # "output": str(output),
            "success": False,
            "init_count": 0,
            "failure_count": 0,
            "init_time_sec": None,
            # "t_first_imu_pose": None,
            # "t_init_finish": None,
            # "error": None,
            "total_yaw_deg": None,
            "yaw_rate_radps": None,
            "a": None,
        }

        try:
            if rviz:
                self.start_rviz()
            self.start_vins(config)
            playback_duration = self.play_bag(bag)
            self.wait_for_bag_completion(playback_duration + 5)
            time.sleep(2)                      # 让 VINS 再写一次最终值
        except Exception as e:
            print(f"harness failed: {e}")
        finally:
            self.stop_all_processes() 

        # 判断是否是一次成功的实验
        stats = self._scan_log({
            "init":  "Initialization finish!",
            # "warn":  "[WARN]",
            # "reset": "reset",
            "failure":"failure detection!"
        })
        # success = (stats["init"] == 1 and stats["failure"] == 0)
        result["init_count"] = stats["init"]
        result["failure_count"] = stats["failure"]
        result["success"] = (stats["init"] == 1 and stats["failure"] == 0)

        t0 = self._time_to_marker("init first imu pose")
        t1 = self._time_to_marker("Initialization finish!")
        if t0 is not None and t1 is not None:
            init_time = t1 - t0
        else:
            init_time = 0.0
        result["init_time_sec"] = init_time

        metrics = self._read_manifest_metrics(Path(bag))
        result.update({
            "total_yaw_deg": metrics["total_yaw_deg"],
            "a": metrics["a"],
            "yaw_rate_radps": metrics["yaw_rate_radps"],
            "manifest_path": metrics["manifest_path"],
        })

        summary_path = output / "summary.json"
        summary_path.write_text(
            json.dumps(result, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        print("***")
        print(f"汇总已写入: {summary_path}")
        print("***")

        return result
    
        
if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description="批量跑vis实验"
    )
    parser.add_argument(
        '--input',
        type=Path,
        default='/run/media/sydai/disk/dataset/swimming_pool/sim/direct-rectangle-001',
        help='所有要跑vins的ros2bag文件'
    )
    parser.add_argument(
        '--workspace',
        type=Path,
        default='/run/media/sydai/disk/git_ws/vins_ws',
        help='vins工作空间'
    )
    parser.add_argument(
        '--vins-config',
        type=Path,
        default='/run/media/sydai/disk/git_ws/vins_ws/src/VINS-Fusion-ROS2/config/simulation/sim_config.yaml',
        help='vins使用的config'
    )
    parser.add_argument(
        '--rviz', 
        action='store_true',
        help='是否开启rviz')
    # 直接在config改
    # parser.add_argument(
    #     '--mode',
    #     type=str,
    #     choices=['imu-mono', 'stereo', 'imu-stereo'],
    #     default='imu'
    # )
    parser.add_argument(
        '--repeat',
        type=int,
        default=1,
        help='每个ros2bag数据跑的次数'
    )
    args = parser.parse_args()

    # ---------- 输入检查 ----------
    if not args.input.exists():
        print(f"错误：文件/文件夹不存在:{args.input}")
        sys.exit(1)
    input_root = args.input if args.input.is_dir() else args.input.parent
    rosbags = []
    rosbags.extend(find_file(input_root, '*.db3'))
    rosbags.extend(find_file(input_root, '*.mcap'))
    if not rosbags:
        print(f"输入{args.input}中未找到可处理文件"); sys.exit(0)

    harness = Harness(args.workspace)
    print("=" * 80)
    print(f"找到 {len(rosbags)} 组 rosbag")
    print("-" * 80)
    for i, bag in enumerate(rosbags, 1):
        print(f"{i:3d}. {Path(bag).parent.name:<30}")
        for j in range(args.repeat):
            print(f"第{j+1}/{args.repeat}次实验:")
            #更新output
            # output = Path(bag).parent if args.repeat==1 else Path(os.path.join(Path(bag).parent, f"{j+1:3d}"))
            output = Path(os.path.join(Path(bag).parent, f"{j+1:03d}"))
            update_config_output_path(args.vins_config, output)

            try:
                result = harness.run(
                    output,
                    args.vins_config,
                    bag,
                    args.rviz
                )
                print("Successful!")
                print("***")
                print(json.dumps(result, indent=2, ensure_ascii=False))
                print("***")
            except KeyboardInterrupt:
                print("Interrupted by user")
                harness.stop_all_processes()
                sys.exit(0)
            except Exception as e:
                print(f"harness failed: {e}")
                continue
            print("-" * 80)
    print("=" * 80)



