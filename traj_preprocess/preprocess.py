import time
import os
import copy
from pydantic import BaseModel, ValidationError
from traj_denoising.denoising import Denoising
from traj_simplify.simplify import Simplify
from traj_supplement.supplement import Supplement
from utils.basic_utils import (read_track_data, examine_and_update_raw_data, update_pd_data, get_traj_info, geojson_to_pd)


class TrajPreprocessItem(BaseModel):
    path: str = ""
    data : object = None
    data_info: object = None
    coord_type: str = "wgs84"
    save_path: str = ""
    denoising_flag: bool = False
    denoising_level: str = "low"
    simplify_flag: bool = False
    simplify_mode: str = "interval_oriented"
    simplify_level: str = "low"
    supplement_flag: bool = False
    supplement_mode: str = "route_plan"
    missing_segment_lower: float = 10.0
    missing_segment_upper: float = 50.0
    logger: object = None


class TrajPreprocess:
    def __init__(self, path="", data=None, data_info=None, coord_type="wgs84",
                 save_path="",
                 denoising_flag=False, denoising_level="low",
                 simplify_flag=False, simplify_mode="interval_oriented", simplify_level="low",
                 supplement_flag=False, supplement_mode="route_plan", missing_segment_lower=10.0,
                 missing_segment_upper=50.0,
                 logger=None):
        self.path = path
        self.data = data
        self.data_info = data_info
        self.coord_type = coord_type
        self.save_path = save_path
        self.denoising_flag = denoising_flag
        self.denoising_level = denoising_level
        self.simplify_flag = simplify_flag
        self.simplify_mode = simplify_mode
        self.simplify_level = simplify_level
        self.supplement_flag = supplement_flag
        self.supplement_mode = supplement_mode
        self.missing_segment_lower = missing_segment_lower
        self.missing_segment_upper = missing_segment_upper
        self.logger = logger

        self.pd_data = None
        self.result_info = None

        base_name = os.path.basename(self.path)
        save_dir_name = os.path.dirname(self.save_path)
        save_base_name = os.path.basename(self.save_path)
        if self.save_path.endswith(".json"):
            # 例如111.json
            if save_dir_name != "" and not os.path.exists(save_dir_name):
                os.makedirs(self.save_path)

            self.save_path = os.path.join(save_dir_name, save_base_name)
        else:
            # 例如''或者data/result_data
            if save_dir_name != "":
                if not os.path.exists(self.save_path):
                    os.makedirs(self.save_path)
                save_base_name = base_name.split(".")[0] + "_preprocessed.json"
                self.save_path = os.path.join(self.save_path, save_base_name)

    def __read_examine_update_traj(self):
        """
        读取轨迹数据并检查关键字段
        :return:
        """
        if self.data is None:
            self.data = read_track_data(self.path)
        else:
            if "type" not in self.data and self.data["type"] != "FeatureCollection":
                raise Exception('轨迹数据为json格式时，需要符合geojson的字段标准')

        self.result_info = copy.deepcopy(self.data)
        self.data_info = self.data["meta"]
        self.pd_data, _ = geojson_to_pd(self.data)

        # 检查轨迹数据：关键字段
        available_flag, self.pd_data, key_msg = examine_and_update_raw_data(self.pd_data)

        # 分情况处理轨迹信息
        if available_flag:
            if key_msg != '':
                self.logger.warning(f"轨迹数据存在异常（不影响抽稀）：{key_msg}")
            # 转换为wgs84坐标系（结果默认为wgs84坐标系）
            if self.coord_type != "wgs84":
                self.logger.info(f"转换坐标系：{self.coord_type} 转换为 wgs84")
                self.pd_data = update_pd_data(self.pd_data, self.coord_type)
        else:
            self.logger.error(f"轨迹数据存在异常：{key_msg}")
            raise Exception(f'轨迹数据存在异常：{key_msg}')

    def process(self):
        # 轨迹预处理主流程，处理过程维持输入的数据格式不变，处理完之后转换为json格式输出
        # 降噪、抽稀、补全，起点、终点始终保持不变，因此中间过程只需要更新坐标、时间戳、速度
        try:
            # 读取轨迹数据并检查
            self.logger.info("轨迹预处理开始")
            self.__read_examine_update_traj()
            self.logger.info("轨迹数据检查完毕")
            # 计算轨迹基础信息
            traj_info = get_traj_info(self.pd_data)
            self.data_info["traj_info"] = traj_info

            # 【降噪】
            if self.denoising_flag:
                self.logger.info("轨迹降噪开始")
                tem_time = time.time()
                # 直接传入轨迹对象
                inputs = {"data":self.result_info, "coord_type": self.coord_type,
                          "save_path": self.save_path,
                          "denoising_level": self.denoising_level,
                          "logger": self.logger}
                traj_denoising = Denoising(**inputs)
                self.result_info = traj_denoising.process()
                self.logger.info(f"轨迹降噪完成，耗时: {round(time.time() - tem_time, 3)} s")
            # 【抽稀】
            if self.simplify_flag:
                self.logger.debug("轨迹抽稀开始")
                tem_time = time.time()
                # 将result_info作为入参传递下去
                inputs = {"data": self.result_info, "coord_type": self.coord_type,
                          "save_path": self.save_path,
                          "simplify_mode": self.simplify_mode, "simplify_level": self.simplify_level,
                          "logger": self.logger}
                traj_simplify = Simplify(**inputs)
                self.result_info = traj_simplify.process()
                self.logger.info(f"轨迹抽稀完成，耗时: {round(time.time() - tem_time, 3)} s")
            # 【补全】
            if self.supplement_flag:
                self.logger.info("轨迹补全开始")
                tem_time = time.time()
                # 将data作为入参传递下去
                inputs = {"data": self.result_info, "coord_type": self.coord_type,
                          "save_path": self.save_path,
                          "supplement_mode": self.supplement_mode, "missing_segment_lower": self.missing_segment_lower,
                          "missing_segment_upper": self.missing_segment_upper,
                          "logger": self.logger}
                traj_supplement = Supplement(**inputs)
                self.result_info = traj_supplement.process()
                self.logger.info(f"轨迹补全完成，耗时: {round(time.time() - tem_time, 3)} s")

            self.logger.info("轨迹预处理顺利完成")

        except Exception as e:
            self.logger.error(f"轨迹预处理发生错误，返回原始轨迹")
            self.logger.error(f"error: {e}")

        return self.result_info


if __name__ == '__main__':
    pass