import os
import json
from pydantic import BaseModel, ValidationError
from utils.basic_utils import (examine_and_update_raw_data, update_pd_data, get_traj_info, pd_to_geojson, geojson_to_pd,
                               get_noise_info, read_track_data)


class DenoisingItem(BaseModel):
    path: str = ""
    data : object = None
    data_info: object = None
    coord_type: str = "wgs84"
    save_path: str = ""
    denoising_level: str = "low"
    logger: object = None


class Denoising(object):
    def __init__(self, path="", data=None, data_info=None, coord_type="wgs84", save_path="",
                 denoising_level="low",
                 logger=None):
        # 要求path必须包含文件名，可以包含文件路径
        # 要求save_path可以包含文件名，可以包含文件路径
        # 要求data为geojson格式（支持直接传入轨迹数据）
        self.path = path
        self.data = data
        # 若为json文件，轨迹信息在meta字段中；若为csv文件，则需要额外传入轨迹信息
        self.data_info = data_info
        self.coord_type = coord_type
        self.save_path = save_path
        self.denoising_level = denoising_level
        self.logger = logger

        # denoising_level越大，表示降噪力度越大，判断异常点的阈值越小（更容易触发）
        self.denoising_limit_info = {
            "low": {"distance_limit": 10000, "time_limit": 3},
            "mid": {"distance_limit": 8000, "time_limit": 2},
            "high": {"distance_limit": 5000, "time_limit": 1},
        }

        self.pd_data = None
        self.coordinates = None
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
                save_base_name = base_name.split(".")[0] + "_denoising.json"
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

        self.result_info = self.data
        self.data_info = self.data["meta"]
        self.pd_data, self.coordinates = geojson_to_pd(self.data)

        # 检查轨迹数据：关键字段
        available_flag, self.pd_data, key_msg = examine_and_update_raw_data(self.pd_data)

        # 分情况处理轨迹信息
        if available_flag:
            if key_msg != '':
                self.logger.warning(f"轨迹数据存在异常（不影响噪点识别）：{key_msg}")
            # 转换为wgs84坐标系（结果默认为wgs84坐标系）
            if self.coord_type != "wgs84":
                self.logger.info(f"转换坐标系：{self.coord_type} 转换为 wgs84")
                self.pd_data = update_pd_data(self.pd_data, self.coord_type)
        else:
            self.logger.error(f"轨迹数据存在异常：{key_msg}")
            raise Exception(f'轨迹数据存在异常：{key_msg}')

    def __denoising_core(self):
        """
        轨迹降噪核心模块：基于距离确定噪点（两步判断）并剔除
        :return:
        """
        # 获取噪点信息
        noise_info, noise_list = get_noise_info(self.pd_data, self.denoising_level)
        if len(noise_list) == 0:
            print("未识别到噪点")
            self.logger.info("未识别到噪点")
            return
        else:
            print(f"识别到{len(noise_list)}个噪点，信息如下：")
            self.logger.info(f"识别到{len(noise_list)}个噪点")

            for i in sorted(noise_list):
                print(i, "\t", self.coordinates[i], "\t")

            # 确定降噪后的轨迹点、坐标
            remained_points = sorted(set(range(len(self.coordinates))) - set(noise_list))
            self.coordinates = self.coordinates[remained_points]
            self.pd_data = self.pd_data.iloc[remained_points]
            self.pd_data.reset_index(drop=True, inplace=True)
        self.data_info["noise_info"] = noise_info
        self.result_info = pd_to_geojson(self.pd_data, self.data_info)

    def process(self):
        """
        轨迹降噪主流程：读取轨迹数据并检查；识别噪点并剔除
        :return: geojson格式的轨迹数据：可能为None（轨迹格式不符合要求）、原始轨迹（降噪过程异常）、降噪后的轨迹（降噪顺利完成）
        """
        try:
            # 读取轨迹数据并检查
            self.__read_examine_update_traj()
            self.logger.info("轨迹数据检查完毕")
            # 计算轨迹基础信息
            traj_info = get_traj_info(self.pd_data)
            self.data_info["traj_info"] = traj_info

            # 识别噪点并剔除
            self.__denoising_core()
            self.logger.info("轨迹降噪成功")
            if self.save_path != "":
                # 结果保存为geojson格式，噪点信息放在meta字段中
                with open(self.save_path, 'w', encoding='utf-8') as f:
                    # 使用json.dump()方法将feature_collection对象写入文件
                    json.dump(self.result_info, f, ensure_ascii=False, indent=4)
        except Exception as e:
            print(f"轨迹降噪失败: {e}")
            self.logger.error(f"轨迹降噪失败: {e}")

        return self.result_info


if __name__ == '__main__':
    pass
