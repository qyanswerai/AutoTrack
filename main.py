import os
from pydantic import ValidationError
from traj_acquisition.traj_acquisition import TrajAcquisitionItem, TrajAcquisition

import logging
log_dir = './logs'
if not os.path.exists(log_dir):
    os.makedirs(log_dir)

log_file_path = os.path.join(log_dir, 'trajectory_acquisition_service.log')

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
    way_points = "116.461028,39.959643;116.441028,39.929643"
    other_params = {"show_fields": "polyline",
                    "profile": "driving-hgv",
                    "format": "geojson"}
    inputs = {"origin": origin,
              "destination": destination,
              # "way_points": way_points,
              "method_type": "ors",
              "coord_type": "bd09ll",
              "other_params": other_params,
              "logger": logger,
              "save_path": save_path,
              "result_type": "json"
              }

    try:
        TrajAcquisitionItem(**inputs)
        traj_acquisition = TrajAcquisition(**inputs)
        traj_acquisition.process()
    except ValidationError as e:
        print(e)
    pass


if __name__ == '__main__':
    traj_acquisition_test()

