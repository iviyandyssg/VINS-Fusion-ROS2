import pytest
import os
import sys
from pathlib import Path
#添加当前脚本文件目录
sys.path.insert(0, str(Path(__file__).parent))
from batch_run_vins import find_file, update_config_output_path, Harness

WORKSPACE = Path(os.environ.get(
    "VINS_WORKSPACE",
    "/run/media/sydai/disk/git_ws/vins_ws"
))
BAG_ROOT = Path(os.environ.get(
    "VINS_BAG_ROOT",
    "/run/media/sydai/disk/dataset/swimming_pool/sim/direct-rectangle-001"
))
CONFIG = Path(os.environ.get(
    "VINS_CONFIG",
    "/run/media/sydai/disk/git_ws/vins_ws/src/VINS-Fusion-ROS2/config/simulation/sim_config.yaml"
))
OUTPUT_ROOT = Path(os.environ.get(
    "VINS_OUTPUT_ROOT",
    "/run/media/sydai/disk/dataset/swimming_pool/test_vins_results"
))


def find_bags(input_root: Path) -> list[Path]:
    bags = []
    bags.extend(find_file(input_root, "*.db3"))
    bags.extend(find_file(input_root, "*.mcap"))
    return sorted(bags)

ALL_BAGS = find_bags(BAG_ROOT)

#fixture为测试提供数据或者资源 scope指定fixture作用范围 
# function default 每个测试函数调用一次
# class 每个测试类调用一次
# module 每个测试py文件调用一次
# package 每个包一次
# session 整个过程只调用一次
@pytest.fixture(scope="session") 
def harness():
    return Harness(str(WORKSPACE))

#参数化，每次用不同的数值
@pytest.mark.parametrize(
    "bag", #函数需要有同名参数
    ALL_BAGS,
    ids=[bag.parent.name for bag in ALL_BAGS],
)
#@pytest.mark.stochastic(samples=3, threshold=0.6)
def test_vins(harness: Harness, bag : Path):
    """对单个rosbag运行vins"""
    output = OUTPUT_ROOT / bag.parent.name
    output.mkdir(parents=True, exist_ok=True)
    update_config_output_path(CONFIG, output)
    result = harness.run(
        output,
        str(CONFIG),
        str(bag),
        False
    )
    #自定义的通过标准
    assert result["success"] is True, (
        f"VINS未成功初始化: init count = {result['init_count']}, failure count = {result['failure_count']}."
    )
    if result["init_time_sec"] is not None:
        assert result["init_time_sec"] < 45.0, (
            f"VINS初始化时间过长: {result['init_time_sec']}"
        )
