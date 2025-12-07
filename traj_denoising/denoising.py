import os
import json
import numpy as np
import pandas as pd
from pydantic import BaseModel, ValidationError
from utils.basic_utils import (cal_haversine_dis, cal_haversine_dis_vector,
                               examine_and_update_raw_data, update_pd_data, cal_traj_info, pd_to_geojson, geojson_to_pd)


class DenoisingItem(BaseModel):
    data_path: str
    data_name: str
    data_type: str = "json"
    coord_type: str = "wgs84"
    save_path: str = ""
    save_type: str = "json"
    denoising_level: str = "low"
    data_info: object = None
    logger: object = None


class Denoising(object):
    def __init__(self, data_path, data_name, data_type='json', data_info=None, logger=None, coord_type="wgs84",
                 save_path="", save_type='json',
                 denoising_level="low"):
        self.data_path = data_path
        self.data_name = data_name
        self.data_type = data_type
        # 若为json文件，轨迹信息在meta字段中；若为csv文件，则需要额外传入轨迹信息
        self.data_info = data_info
        self.logger = logger
        self.coord_type = coord_type
        self.save_path = save_path
        self.save_type = save_type
        self.denoising_level = denoising_level

        # denoising_level越大，表示降噪力度越大，判断异常点的阈值越小（更容易触发）
        self.denoising_limit_info = {
            "low": {"distance_limit": 10000, "time_limit": 3},
            "mid": {"distance_limit": 8000, "time_limit": 2},
            "high": {"distance_limit": 5000, "time_limit": 1},
        }

        self.data = None
        self.pd_data = None
        self.coordinates = None

        self.result_info = None

    def __read_examine_update_traj(self):
        """
        读取轨迹数据并检查关键字段
        :return:
        """
        if self.data_type == "json":
            with open(os.path.join(self.data_path, self.data_name), encoding='utf-8') as f:
                self.data = json.load(f)
                self.result_info = self.data
                if "type" not in self.data and self.data["type"] != "FeatureCollection":
                    self.logger.error("轨迹数据为json格式，但不符合geojson的字段标准")
                    raise Exception('轨迹数据为json格式时，需要符合geojson的字段标准')
                self.data_info = self.data["meta"]

                self.pd_data, self.coordinates = geojson_to_pd(self.data)

        elif self.data_type == "csv":
            self.data = pd.read_csv(os.path.join(self.data_path, self.data_name))
            self.pd_data = self.data.copy(deep=True)
            self.coordinates = self.pd_data[["lng", "lat"]].values

            if self.data_info is None:
                self.data_info = {}
            self.result_info = pd_to_geojson(self.pd_data, self.data_info)
        else:
            self.logger.error("暂不支持该类轨迹文件，请转换为json或csv格式")
            raise Exception("暂不支持该类轨迹文件，请转换为json或csv格式")

        # 检查轨迹数据：关键字段
        available_flag, self.pd_data, key_msg = examine_and_update_raw_data(self.pd_data)

        # 分情况处理轨迹信息
        if available_flag:
            if key_msg != '':
                self.logger.warning(f"轨迹数据存在异常（不影响噪点识别）：{key_msg}")
            # 转换为WGS84坐标系
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
        # 轨迹降噪
        distance_limit = self.denoising_limit_info[self.denoising_level]["distance_limit"]
        time_limit = self.denoising_limit_info[self.denoising_level]["time_limit"]

        # 向量化计算距离
        distance_list = cal_haversine_dis_vector(self.pd_data)
        # Step1：根据距离阈值确定噪点（初筛），记录轨迹点索引、距离
        detected_noise_segments = np.where(distance_list >= distance_limit)[0]
        segment_dis_list = distance_list[detected_noise_segments]
        # 调整为轨迹点对：列表表达式；广播机制 + 按列堆叠
        detected_noise_segments = np.column_stack((detected_noise_segments, detected_noise_segments + 1))

        # Step2：根据相邻的noise_segment，判断要剔除的噪点
        # 记录要剔除的轨迹点
        noise_list = []
        for i in range(len(detected_noise_segments) - 1):
            left_index = detected_noise_segments[i][0]
            right_index = detected_noise_segments[i + 1][1]
            cur_point = self.coordinates[left_index]
            next_point = self.coordinates[right_index]
            dis = cal_haversine_dis(cur_point, next_point)
            if (
                    segment_dis_list[i] >= time_limit * dis
                    and segment_dis_list[i + 1] >= time_limit * dis
            ):
                noise_list.extend(list(range(left_index + 1, right_index)))

        if len(noise_list) == 0:
            print("未识别到噪点")
            self.logger.info("未识别到噪点")
            self.data_info["noise_info"] = {"noise_num": len(noise_list)}
            return
        else:
            print(f"识别到{len(noise_list)}个噪点，信息如下：")
            self.logger.info(f"识别到{len(noise_list)}个噪点")
            self.data_info["noise_info"] = {"noise_num": len(noise_list),
                                            "noise_points": self.pd_data.iloc[noise_list].to_dict(orient='records')}

            for i in sorted(noise_list):
                print(i, "\t", self.coordinates[i], "\t")

            # 确定降噪后的轨迹点、坐标
            remained_points = sorted(set(range(len(self.coordinates))) - set(noise_list))
            self.coordinates = self.coordinates[remained_points]
            self.pd_data = self.pd_data.iloc[remained_points]
            self.pd_data.reset_index(drop=True, inplace=True)

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
            traj_info = cal_traj_info(self.pd_data)
            self.data_info["traj_info"] = traj_info

            # 识别噪点并剔除
            self.__denoising_core()
            self.logger.info("轨迹降噪成功")
            if self.save_path != "":
                # 结果保存为geojson格式，噪点信息放在meta字段中
                file_path = os.path.join(self.save_path, self.data_name.split('.')[0] + '_denoising.json')
                with open(file_path, 'w', encoding='utf-8') as f:
                    # 使用json.dump()方法将feature_collection对象写入文件
                    json.dump(self.result_info, f, ensure_ascii=False, indent=4)
        except Exception as e:
            print(f"轨迹降噪失败: {e}")
            self.logger.error(f"轨迹降噪失败: {e}")

        return self.result_info


if __name__ == '__main__':
    path = r'../data/raw_data'
    save_path = r'../data/result_data'

    # 【孤立噪点】
    file = '孤立噪点.json'

    # 【多个噪点集中分布】
    # file = '多个噪点集中分布_1.json'
    # file = '多个噪点集中分布_2.json'

    # 【多个噪点反复横跳】
    # file = '多个噪点反复横跳.json'

    params = {'data_path': path, 'data_name': file, 'save_path': save_path}

    # file = '孤立噪点.csv'
    # params = {'data_path': path, 'data_name': file, 'save_path': save_path, 'data_type': 'csv'}

    denoising = Denoising(**params)
    denoising.process()
    print("finished")
