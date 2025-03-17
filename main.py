import os
import json
from pydantic import BaseModel, ValidationError
from traj_acquisition.traj_acquisition import TrajAcquisition

import logging
log_dir = './logs'
if not os.path.exists(log_dir):
    os.makedirs(log_dir)

log_file_path = os.path.join(log_dir, 'trajectory_compare_service.log')

# 配置日志记录器
logging.basicConfig(
    level=logging.INFO,  # 设置日志级别
    # 格式化日志输出
    format='%(asctime)s - %(name)s - %(filename)s - %(levelname)s - %(funcName)s - %(lineno)d - %(message)s',
    filename=log_file_path,  # 日志文件名
    filemode='a'  # 追加模式
)

logger = logging.getLogger(__name__)


class TrajAcquisitionItem(BaseModel):
    # 对于base_data、raw_data，仅校验其是否存在，后续在TrajectoryCompare初始化时根据data_type进行字段校验
    origin: str
    destination: str
    way_points: str = ""
    method_type: str = "amap"
    coord_type: str = "gcj02"
    other_params: dict = None
    save_path: str = ""


if __name__ == '__main__':
    path = r'data/raw_data'
    # save_path = ""

    # 起点、终点、中间点的形式符合高德驾车路径规划API的要求
    origin = "116.481028,39.989643"
    destination = "116.434446,39.90816"
    way_points = "116.461028,39.959643;116.441028,39.929643"
    other_params = {"show_fields": "polyline"}
    params = {"origin": origin,
              # "destination": destination,
              # "way_points": way_points,
              "method_type": "ors",
              "coord_type": "bd09ll",
              "other_params": other_params
              }

    try:
        TrajAcquisitionItem(**params)
        traj_acquisition = TrajAcquisition(**params)
        traj_acquisition.process()
    except ValidationError as e:
        print(e)
