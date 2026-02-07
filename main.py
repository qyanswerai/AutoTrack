import os
import json
from pydantic import ValidationError
from traj_acquisition.traj_acquisition import TrajAcquisitionItem, TrajAcquisition

from traj_denoising.denoising import Denoising, DenoisingItem
from traj_simplify.simplify import Simplify, SimplifyItem
from traj_supplement.supplement import Supplement, SupplementItem

import logging
log_dir = './logs'
if not os.path.exists(log_dir):
    os.makedirs(log_dir)

log_file_path = os.path.join(log_dir, 'trajectory_service.log')

# 配置日志记录器
logging.basicConfig(
    level=logging.INFO,  # 设置日志级别
    # 格式化日志输出
    format='%(asctime)s - %(name)s - %(filename)s - %(levelname)s - %(funcName)s - %(lineno)d - %(message)s',
    filename=log_file_path,  # 日志文件名
    filemode='a'  # 追加模式
)

logger = logging.getLogger(__name__)


def traj_acquisition_test():
    """
    测试轨迹获取功能
    :return:
    """
    save_path = r"data/result_data"

    # 起点、终点、中间点的形式符合高德驾车路径规划API的要求
    origin = "116.481028,39.989643"
    destination = "116.434446,39.90816"
    # way_points = "116.461028,39.959643;116.441028,39.929643"
    # origin = "121.418634,31.223663"
    # destination = "121.018527,31.098996"
    # way_points = "121.167664,31.147555"
    other_params = {"show_fields": "polyline",
                    "profile": "driving-hgv",
                    "format": "geojson"}

    inputs = {"origin": origin,
              "destination": destination,
              # "way_points": way_points,
              "method_type": "amap",
              "coord_type": "gcj02",
              # "result_coord_type": "gcj02",
              "other_params": other_params,
              "logger": logger,
              "save_path": save_path,
              "simulate_flag": False
              }

    try:
        # 虽然logger不是必需字段，但是为了代码正常执行需要传入
        TrajAcquisitionItem(**inputs)
        traj_acquisition = TrajAcquisition(**inputs)
        traj_data = traj_acquisition.process()
        return traj_data
    except ValidationError as e:
        print(e)
        return None

def traj_denoising_test():
    """
    测试轨迹降噪功能
    :return:
    """
    # 【孤立噪点】
    path = r'data/raw_data/孤立噪点.json'
    save_path = r'data/result_data'

    # file = 'data/raw_data/孤立噪点.csv'
    # inputs = {"path": path, "save_path": save_path, "logger": logger}

    # 【多个噪点集中分布】
    # path = r'data/raw_data/多个噪点集中分布_1.json'
    # path = r'data/raw_data/多个噪点集中分布_2.json'

    # 【多个噪点反复横跳】
    # path = r'data/raw_data/多个噪点反复横跳.json'

    inputs = {"path": path, "save_path": save_path, "logger": logger}

    # with open(path, encoding='utf-8') as f:
    #     data = json.load(f)
    # inputs = {"path": path, "save_path": save_path, "data": data, "logger": logger}

    try:
        # 虽然logger不是必需字段，但是为了代码正常执行需要传入
        DenoisingItem(**inputs)
        traj_denoising = Denoising(**inputs)
        traj_data = traj_denoising.process()
        return traj_data
    except ValidationError as e:
        print(e)
        return None

def traj_simplify_test():
    """
    测试轨迹抽稀功能
    :return:
    """
    # 【孤立噪点】
    path = r'data/raw_data/孤立噪点.json'
    save_path = r'data/result_data'

    inputs = {"path": path, "save_path": save_path, 'simplify_mode': "downclocking", "logger": logger}

    # with open(path, encoding='utf-8') as f:
    #     data = json.load(f)
    # inputs = {"path": path, "data": data, "save_path": save_path, 'simplify_mode': "downclocking", "logger": logger}

    try:
        # 虽然logger不是必需字段，但是为了代码正常执行需要传入
        SimplifyItem(**inputs)
        traj_simplify = Simplify(**inputs)
        traj_data = traj_simplify.process()
        return traj_data
    except ValidationError as e:
        print(e)
        return None

def traj_supplement_test():
    """
    测试轨迹补全功能
    :return:
    """
    # 【1个缺失段】
    path = r'data/raw_data/缺失段.json'
    save_path = r'data/result_data'

    # inputs = {'path': path, "save_path": save_path, 'supplement_mode': 'interpolate', "logger": logger}

    with open(path, encoding='utf-8') as f:
        data = json.load(f)
    inputs = {"path": path, "data": data, "save_path": save_path, "supplement_mode": "interpolate", "logger": logger}

    try:
        # 虽然logger不是必需字段，但是为了代码正常执行需要传入
        SupplementItem(**inputs)
        traj_supplement = Supplement(**inputs)
        traj_data = traj_supplement.process()
        return traj_data
    except ValidationError as e:
        print(e)
        return None


if __name__ == '__main__':
    # 测试轨迹获取功能
    # traj_info = traj_acquisition_test()

    # 测试轨迹降噪功能
    # traj_info = traj_denoising_test()

    # 测试轨迹抽稀功能
    # traj_info = traj_simplify_test()

    # 测试轨迹补全功能
    traj_info = traj_supplement_test()

    print('finished')

