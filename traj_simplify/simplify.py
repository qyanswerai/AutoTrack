import os
import json
import numpy as np
import pandas as pd
from pyproj import CRS, Transformer
from shapely.geometry import Point, LineString
from pydantic import BaseModel, ValidationError
from utils.basic_utils import (cal_haversine_dis, cal_bearing,
                               examine_and_update_raw_data, update_pd_data, cal_traj_info, pd_to_geojson, geojson_to_pd)


class SimplifyItem(BaseModel):
    data_path: str
    data_name: str
    data_type: str = "json"
    coord_type: str = "wgs84"
    save_path: str = ""
    save_type: str = "json"
    simplify_mode: str = "interval_oriented"
    simplify_level: str = "low"
    data_info: object = None
    logger: object = None


class Simplify(object):
    def __init__(self, data_path, data_name, data_type='json', data_info=None, logger=None, coord_type="wgs84",
                 save_path="", save_type='json',
                 simplify_mode='interval_oriented', simplify_level="low"):
        self.data_path = data_path
        self.data_name = data_name
        self.data_type = data_type
        # 若为json文件，轨迹信息在meta字段中；若为csv文件，则需要额外传入轨迹信息
        self.data_info = data_info
        self.logger = logger
        self.coord_type = coord_type
        self.save_path = save_path
        self.save_type = save_type
        self.simplify_mode = simplify_mode
        self.simplify_level = simplify_level

        # simplify_level越大，表示抽稀力度越大，保留的轨迹点越少
        # interval_oriented：参数表示轨迹点期望采样间隔
        # downclocking：参数表示轨迹点期望下采样频率（若为1，则表示跳过1个点保留1个点）
        # rdp：参数表示drp算法的距离阈值
        self.simplify_info = {
            "interval_oriented": {"low": 5, "mid": 10, "high": 15},
            "downclocking": {"low": 1, "mid": 2, "high": 3},
            "rdp": {"low": 5, "mid": 8, "high": 10}
        }
        self.core_param = self.simplify_info[self.simplify_mode][self.simplify_level]

        # 采用rdp方式时，默认不进行重投影
        self.reproject_flag = False

        self.data = None
        self.pd_data = None
        self.coordinates = None

        self.result_info = None

        self.from_crs = CRS('EPSG: 4326')
        self.to_crs = CRS('EPSG: 32648')

        self.trans_4326 = Transformer.from_crs(self.from_crs, self.to_crs, always_xy=True)
        self.trans_32648 = Transformer.from_crs(self.to_crs, self.from_crs, always_xy=True)

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
                self.logger.warning(f"轨迹数据存在异常（不影响抽稀）：{key_msg}")
            # 转换为wgs84坐标系（结果默认为wgs84坐标系）
            if self.coord_type != "wgs84":
                self.logger.info(f"转换坐标系：{self.coord_type} 转换为 wgs84")
                self.pd_data = update_pd_data(self.pd_data, self.coord_type)
        else:
            self.logger.error(f"轨迹数据存在异常：{key_msg}")
            raise Exception(f'轨迹数据存在异常：{key_msg}')

    def __rdp_process(self):
        # 轨迹抽稀
        def cal_projection_distance(left_p, right_p, other_p):
            # 实现方式1：
            # 构造shapely库的Point、LineString对象，使用函数得到点到线的距离
            # Point.distance获取点到线的最小距离：若点在线的范围内，返回投影距离；若不在范围内，则大概率返回点到线的端点的距离（受线形影响）
            # points_utm = [self.trans_4326.transform(lng, lat) for lng, lat in [left_p, right_p, other_p]]
            # line_utm = LineString(points_utm[:-1])
            # h_1 = Point(points_utm[-1]).distance(line_utm)

            # 实现方式2：
            # 计算点之间的距离，根据海伦公式（Heron’s formula）计算三角形的面积（若共线则为0），根据面积计算某条边的高
            a = cal_haversine_dis(left_p, other_p)
            b = cal_haversine_dis(right_p, other_p)
            c = cal_haversine_dis(left_p, right_p)
            if a + b > c and b + c > a and c + a > b:
                s = (a + b + c) / 2
                h_2 = 2 * np.sqrt(s * (s - a) * (s - b) * (s - c)) / c
            else:
                h_2 = 0

            # 【说明】当点不在线的范围内时（比如噪点），根据投影计算的距离比根据三角形计算的数值大，对于确定间距最大的点无影响；
            #        当点在线的范围内时，两种计算方式的结果基本相等
            # print(f'根据投影计算的距离为{round(h_1,2)}，根据三角形计算的距离为{round(h_2,2)}')
            return h_2

        def rdp_core(left, right):
            if right - left < 2:
                return [left, right]

            # 若首末点坐标相同，则剔除中间的其他点
            # if self.coordinates[left] == self.coordinates[right]:
            #     return [left, right]

            if np.all(self.coordinates[left] == self.coordinates[right]):
                return [left, right]

            max_dis = 0.0
            max_i = 0
            for i in range(left + 1, right):
                distance = cal_projection_distance(
                    self.coordinates[left], self.coordinates[right], self.coordinates[i]
                )
                if distance > max_dis:
                    max_i = i
                    max_dis = distance

            if max_dis > self.core_param:
                results1 = rdp_core(left, max_i)
                results2 = rdp_core(max_i, right)
                return results1[:-1] + results2
            else:
                return [left, right]

        remained = rdp_core(0, len(self.coordinates) - 1)
        self.logger.info(f"是否将要剔除的轨迹点重投影保持轨迹点数量不变:{self.reproject_flag}")
        # 若要重投影，则找到被剔除点，使用投影坐标替换原坐标
        if self.reproject_flag:
            simplified = []
            updated_info = []
            for left, right in zip(remained, remained[1:]):
                if left + 1 == right:
                    continue
                # 找到被剔除点，使用投影坐标替换原坐标
                for other in range(left + 1, right):
                    points_utm = [
                        self.trans_4326.transform(lng, lat)
                        for lng, lat in [
                            self.coordinates[left],
                            self.coordinates[right],
                            self.coordinates[other],
                        ]
                    ]
                    line_utm = LineString(points_utm[:-1])
                    # 对于line.project(point)，若点的投影点在线的起点之前，则返回0；若在线的终点之后，则返回线的长度；若在线上，则返回起点到投影点之间的长度
                    # line.interpolate(line.project(point))，若点的投影点在线的起点之前，则返回起点
                    point_pro = line_utm.interpolate(
                        line_utm.project(Point(points_utm[-1]))
                    )
                    x, y = point_pro.x, point_pro.y
                    lng, lat = self.trans_32648.transform(x, y)
                    # self.coordinates[other] = [lng, lat]
                    simplified.append(other)
                    updated_info.append([lng, lat])
                    # 计算航向角
                    bearing = cal_bearing(
                        *self.coordinates[left], *self.coordinates[right]
                    )
                    updated_info[-1].append(bearing)
            remained = list(range(len(self.coordinates)))
            return {
                "remained": remained,
                "simplified": simplified,
                "updated_info": updated_info,
            }
        else:
            return {"remained": remained}

    def __simplify_core(self):
        """
        轨迹抽稀核心模块：降频、滑动窗口、rdp
        :return:
        """
        if "interval_oriented" == self.simplify_mode:
            # 剔除部分轨迹点以达到期望的平均采样间隔
            # 初始化累计误差为0，若大于期望值则更新
            cumulative_time_bias = 0
            # 保留第一个轨迹点
            remained_points = [0]
            timestamps = self.pd_data['timestamp'].values.tolist()
            for i in range(len(timestamps) - 1):
                interval = (timestamps[i + 1] - timestamps[i]) / 1000
                # 计算cumulative_time_bias，若cumulative_time_bias >= 期望值，则保留轨迹点，并更新cumulative_time_bias
                cumulative_time_bias += interval
                if cumulative_time_bias >= self.core_param:
                    remained_points.append(i + 1)
                    cumulative_time_bias %= self.core_param
        elif "downclocking" == self.simplify_mode:
            # 默认从第一个轨迹点开始
            remained_points = list(range(0, len(self.coordinates), self.core_param + 1))

        elif "rdp" == self.simplify_mode:
            result = self.__rdp_process()
            remained_points = result["remained"]
            # 更新坐标、航向角
            if "simplified" in result:
                self.pd_data.loc[result["simplified"], ["lng", "lat", "direction"]] = (
                    result["updated_info"]
                )
        else:
            self.logger.error("暂不支持该抽稀方式，请换用有效的抽稀方式")
            raise Exception("暂不支持该抽稀方式，请换用有效的抽稀方式")

        self.logger.info(f"抽稀后剩余{len(remained_points)}个轨迹点")
        self.data_info["simplify_info"] = {"raw_num": len(self.coordinates), "remained_num": len(remained_points)}

        # 确定抽稀后的轨迹点、坐标
        self.coordinates = self.coordinates[remained_points]
        self.pd_data = self.pd_data.iloc[remained_points]
        self.pd_data.reset_index(drop=True, inplace=True)

        self.result_info = pd_to_geojson(self.pd_data, self.data_info)

    def process(self):
        """
        轨迹抽稀主流程：读取轨迹数据并检查；过滤轨迹点
        :return: geojson格式的轨迹数据：可能为None（轨迹格式不符合要求）、原始轨迹（抽稀过程异常）、抽稀后的轨迹（抽稀顺利完成）
        """
        try:
            # 读取轨迹数据并检查
            self.__read_examine_update_traj()
            self.logger.info("轨迹数据检查完毕")
            # 计算轨迹基础信息
            traj_info = cal_traj_info(self.pd_data)
            self.data_info["traj_info"] = traj_info

            # 识别噪点并剔除
            self.__simplify_core()
            self.logger.info("轨迹抽稀成功")
            if self.save_path != "":
                # 结果保存为geojson格式，抽稀前后的轨迹点数量放在meta字段中
                file_path = os.path.join(self.save_path, self.data_name.split('.')[0] + '_simplify.json')
                with open(file_path, 'w', encoding='utf-8') as f:
                    # 使用json.dump()方法将feature_collection对象写入文件
                    json.dump(self.result_info, f, ensure_ascii=False, indent=4)
        except Exception as e:
            print(f"轨迹抽稀失败: {e}")
            self.logger.error(f"轨迹抽稀失败: {e}")

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
    # params = {'data_path': path, 'data_name': file, 'save_path': save_path}
    params = {'data_path': path, 'data_name': file, 'save_path': save_path, 'simplify_mode': 'rdp'}

    # file = '孤立噪点.csv'
    # params = {'data_path': path, 'data_name': file, 'save_path': save_path, 'data_type': 'csv'}

    simplify = Simplify(**params)
    simplify.process()
    print("finished")
