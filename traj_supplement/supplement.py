import os
import json
import numpy as np
import pandas as pd
from pyproj import CRS, Transformer
from shapely.geometry import Point, LineString
from pydantic import BaseModel, ValidationError
from traj_acquisition.traj_acquisition import TrajAcquisition, TrajAcquisitionItem
from utils.basic_utils import (cal_haversine_dis, cal_bearing,
                               examine_and_update_raw_data, update_pd_data, cal_traj_info, pd_to_geojson, geojson_to_pd)


class SupplementItem(BaseModel):
    data_path: str
    data_name: str
    data_type: str = "json"
    coord_type: str = "wgs84"
    save_path: str = ""
    save_type: str = "json"
    supplement_mode: str = "route_plan"
    missing_segment_lower: float = 10.0
    missing_segment_upper: float = 50.0
    data_info: object = None
    logger: object = None


class Supplement(object):
    def __init__(self, data_path, data_name, data_type='json', data_info=None, logger=None, coord_type="wgs84",
                 save_path="", save_type='json',
                 supplement_mode="route_plan", missing_segment_lower=10.0, missing_segment_upper=50.0):
        self.data_path = data_path
        self.data_name = data_name
        self.data_type = data_type
        # 若为json文件，轨迹信息在meta字段中；若为csv文件，则需要额外传入轨迹信息
        self.data_info = data_info
        self.logger = logger
        self.coord_type = coord_type
        self.save_path = save_path
        self.save_type = save_type
        self.supplement_mode = supplement_mode
        self.missing_segment_lower = missing_segment_lower
        self.missing_segment_upper = missing_segment_upper

        # supplement_mode：
        # 方式1：route_plan，调用【轨迹获取模块 traj acquisition】，使用API的路径规划能力补全缺失段
        # 方式2：interpolate，对缺失段等距插值

        # 缺失段上下限（单位；km）：missing_segment_lower ~ missing_segment_upper，在范围内的缺失段需进行补全

        # 等距插值参数：间隔100米
        self.interpolate_interval = 100
        # 指定补全的轨迹点的瞬时速度为200km/h，一定程度能够避免后续被识别为异常段
        self.virtual_speed = 200

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

    def interpolate_point(self, start, end, distance, start_time, interval):
        """
        缺失段起终点连线，线性等距插值
        :param start: 缺失段起点
        :param end: 缺失段终点
        :param distance: 缺失段长度
        :param start_time: 缺失段起点时间戳
        :param interval: 缺失段时间间隔
        :return: 补全的轨迹点（不包含缺失段起终点）
        """
        points = []

        direction = cal_bearing(*start, *end)

        point_utm = [self.trans_4326.transform(lng, lat) for lng, lat in [start, end]]
        line = LineString(point_utm)

        # 直线等距插值，默认100m一个点
        for d in range(self.interpolate_interval, int(distance), self.interpolate_interval):
            point = line.interpolate(d)
            x, y = point.x, point.y
            lng, lat = self.trans_32648.transform(x, y)
            t = start_time + d / distance * interval
            points.append([lng, lat, t])

        data = pd.DataFrame(points, columns=['lng', 'lat', 'timestamp'])
        data["direction"] = direction
        # 指定补全的轨迹点的瞬时速度，默认为200km/h
        data["speed"] = self.virtual_speed
        return data

    def update_shortest_path(self, path, start_time, interval):
        """
        完善路径规划所获取的轨迹字段
        :param path: 路径规划获取的轨迹坐标（包含缺失段起终点）
        :param start_time: 缺失段起点时间戳
        :param interval: 缺失段时间间隔
        :return: 补全的轨迹点（不包含缺失段起终点）
        """
        points = []
        # 轨迹点过滤：因为轨迹点可能存在偏移，若偏移到路的另一侧则据此得到的最短路会存在多余的掉头段
        # 根据起点、终点连线的夹角进行简单过滤：若夹角在[45,135][225,315]范围内，则根据起终点经度过滤；否则根据纬度过滤
        # 经测试，效果不佳，暂时不进行调整 -_-
        # direction = cal_bearing(*path[0], *path[-1])
        # lng_range = [min(path[0][0], path[-1][0]), max(path[0][0], path[-1][0])]
        # lat_range = [min(path[0][1], path[-1][1]), max(path[0][1], path[-1][1])]
        # if 45 < direction < 135 or 225 < direction < 315:
        #     path = [point for point in path if lng_range[0] <= point[0] <= lng_range[1]]
        # else:
        #     path = [point for point in path if lat_range[0] <= point[1] <= lat_range[1]]

        # 计算direction、timestamp
        point_utm = [self.trans_4326.transform(lng, lat) for lng, lat in path]
        line = LineString(point_utm)

        for i in range(1, len(path) - 1):
            d = line.project(Point(point_utm[i]))
            t = start_time + d / line.length * interval
            direction = cal_bearing(*path[i - 1], *path[i])
            points.append([path[i][0], path[i][1], t, direction])

        data = pd.DataFrame(points, columns=['lng', 'lat', 'timestamp', 'direction'])
        # 指定补全的轨迹点的瞬时速度，默认为200km/h
        data["speed"] = self.virtual_speed
        return data

    def get_supplement_point_data(self, missing_segments):
        """
        根据缺失段确定补全段：路径规划、等距插值
        :param missing_segments: 缺失段信息
        :return: 各个缺失段需补全的轨迹点
        """
        supplement_list = []
        # 执行【轨迹获取模块】：默认调用高德路径规划API获取轨迹
        if "route_plan" == self.supplement_mode:
            self.logger.info("调用【轨迹获取模块】实现缺失段补全，默认调用高德路径规划API获取轨迹")
            print("调用【轨迹获取模块】实现缺失段补全，默认调用高德路径规划API获取轨迹")
            for missing_segment in missing_segments:
                point_i = [missing_segment['start']['lng'], missing_segment['start']['lat']]
                time_i = missing_segment['start']['timestamp']
                point_j = [missing_segment['end']['lng'], missing_segment['end']['lat']]
                distance = missing_segment['length']
                delta_t = missing_segment['interval']

                # 起点、终点、中间点的形式符合高德驾车路径规划API的要求
                origin = str(missing_segment['start']['lng']) + "," + str(missing_segment['start']['lat'])
                destination = str(missing_segment['end']['lng']) + "," + str(missing_segment['end']['lat'])
                # 采用高德、ors获取轨迹需要一些额外的参数
                other_params = {"show_fields": "polyline",
                                "profile": "driving-hgv",
                                "format": "geojson"}
                # 入参都会被转换为wgs84坐标系，轨迹获取模块默认输出为wgs84坐标系
                inputs = {"origin": origin,
                          "destination": destination,
                          "method_type": "amap",
                          "coord_type": "wgs84",
                          "other_params": other_params,
                          "logger": self.logger
                          }
                TrajAcquisitionItem(**inputs)
                traj_acquisition = TrajAcquisition(**inputs)
                geojson_data = traj_acquisition.process()

                if geojson_data is None:
                    # 使用线性插值补全
                    print(f"缺失段 {str(point_i)} -> {str(point_j)}调用【轨迹获取模块】补全失败，转而进行线性插值补全")
                    interpolate_data = self.interpolate_point(point_i, point_j, distance, time_i, delta_t)
                    supplement_list.append(interpolate_data)
                else:
                    # geojson转换为Dataframe
                    api_data, _ = geojson_to_pd(geojson_data)

                    supplement_route = api_data[['lng', 'lat']].values.tolist()
                    supplement_route.insert(0, point_i)
                    supplement_route.append(point_j)
                    api_data = self.update_shortest_path(supplement_route, time_i, delta_t)
                    supplement_list.append(api_data)

            return supplement_list
        elif "interpolate" == self.supplement_mode:
            self.logger.info("进行线性插值补全")
            print("进行线性插值补全")
            for missing_segment in missing_segments:
                point_i = [missing_segment['start']['lng'], missing_segment['start']['lat']]
                time_i = missing_segment['start']['timestamp']
                point_j = [missing_segment['end']['lng'], missing_segment['end']['lat']]
                distance = missing_segment['length']
                delta_t = missing_segment['interval']
                interpolate_data = self.interpolate_point(point_i, point_j, distance, time_i, delta_t)
                supplement_list.append(interpolate_data)

            return supplement_list
        else:
            self.logger.error(f"暂不支持{self.supplement_mode}，请换用route_plan或者interpolate进行轨迹补全")
            raise Exception(f"暂不支持{self.supplement_mode}，请换用route_plan或者interpolate进行轨迹补全")

    def __supplement_core(self):
        """
        轨迹补全核心模块：识别缺失段、确定补全段
        :return:
        """
        # Step1：识别缺失段
        # 相邻点的距离在指定的缺失段上下限内则进行记录
        missing_segments = []
        for i in range(len(self.coordinates) - 1):
            point_i = self.coordinates[i]
            point_j = self.coordinates[i + 1]
            distance = cal_haversine_dis(point_i, point_j)
            if self.missing_segment_lower * 1000 <= distance <= self.missing_segment_upper * 1000:

                time_i = self.pd_data.loc[i, 'timestamp']
                time_j = self.pd_data.loc[i + 1, 'timestamp']
                delta_t = time_j - time_i

                # {'start':{'lng','lat','timestamp'}, 'end':{'lng','lat','timestamp'}, 'length', 'interval'}
                missing_segments.append({'start': {'lng': point_i[0],'lat': point_i[1], 'timestamp': time_i},
                                         'end': {'lng': point_j[0],'lat': point_j[1], 'timestamp': time_j},
                                         'length': distance, 'interval': delta_t})

        if len(missing_segments) == 0:
            self.logger.info("未识别到缺失段")
            print("未识别到缺失段")
            return

        self.logger.info(f"识别到{len(missing_segments)}个缺失段，信息如下：")
        print(f"识别到{len(missing_segments)}个缺失段，信息如下：")
        print(missing_segments)

        # Step2：补全缺失段
        # 方式1：直线等距插值
        # 方式2：调用轨迹获取模块（不使用该模块的轨迹增强及字段补全功能）
        supplement_list = self.get_supplement_point_data(missing_segments)
        supplement_data = pd.concat(supplement_list, ignore_index=True)
        # 修改missing_segments中的timestamp类型，避免保存为json文件时报错
        for missing_segment in missing_segments:
            missing_segment['start']['timestamp'] = str(missing_segment['start']['timestamp'])
            missing_segment['end']['timestamp'] = str(missing_segment['end']['timestamp'])
            missing_segment['interval'] = str(missing_segment['interval'])
        self.data_info["missing_supplement_info"] = {"missing_segment_num": len(missing_segments),
                                                     "missing_info": missing_segments,
                                                     "supplement_mode": self.supplement_mode,
                                                     "supplement_points_num": len(supplement_data)}

        # 拼接补全的轨迹点
        self.pd_data = pd.concat([self.pd_data, supplement_data])

        self.pd_data['timestamp'] = self.pd_data['timestamp'].astype('int64')
        # 按照timestamp排序，指定排序方式（稳定排序：值相同时先后顺序保持不变）
        self.pd_data.sort_values(by=['timestamp'], inplace=True, kind='mergesort')
        # 剔除timestamp相同的轨迹点（若缺失段两端点的timestamp的时间戳相差很小，则可能存在）
        self.pd_data.drop_duplicates(subset='timestamp', keep='first', inplace=True)
        self.pd_data.reset_index(drop=True, inplace=True)
        self.coordinates = self.pd_data[['lng', 'lat']].values.tolist()

        self.result_info = pd_to_geojson(self.pd_data, self.data_info)

    def process(self):
        """
        轨迹补全主流程：读取轨迹数据并检查；识别缺失并补全
        :return: geojson格式的轨迹数据：可能为None（轨迹格式不符合要求）、原始轨迹（补全过程异常）、补全后的轨迹（补全顺利完成）
        """
        try:
            # 读取轨迹数据并检查
            self.__read_examine_update_traj()
            self.logger.info("轨迹数据检查完毕")
            # 计算轨迹基础信息
            traj_info = cal_traj_info(self.pd_data)
            self.data_info["traj_info"] = traj_info

            # 识别缺失段并补全
            self.__supplement_core()
            self.logger.info("轨迹补全成功")
            if self.save_path != "":
                # 结果保存为geojson格式，缺失段及补全信息放在meta字段中
                file_path = os.path.join(self.save_path, self.data_name.split('.')[0] + '_supplement.json')
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(self.result_info, f, ensure_ascii=False, indent=4)
        except Exception as e:
            print(f"轨迹补全失败: {e}")
            self.logger.error(f"轨迹补全失败: {e}")

        return self.result_info


if __name__ == '__main__':

    path = r'../data/raw_data'
    save_path = r'../data/result_data'

    # 【孤立噪点】
    # file = '1765598740674.json'

    # 读取已有轨迹，剔除中间1/3的轨迹点，构造缺失段
    # with open(os.path.join(path, file), encoding='utf-8') as f:
    #     data = json.load(f)
    # data_info = data['meta']
    # pd_data, _ = geojson_to_pd(data)
    # threshold = len(pd_data) // 3
    # print(len(pd_data))
    # df_subset = pd.concat([pd_data.iloc[:threshold], pd_data.iloc[-threshold:]], ignore_index=True)
    # print(len(df_subset))
    # data = pd_to_geojson(df_subset, data_info)
    # with open(os.path.join(path, '缺失段.json'), 'w', encoding='utf-8') as f:
    #     json.dump(data, f, ensure_ascii=False, indent=4)

    file = '缺失段.json'
    params = {'data_path': path, 'data_name': file, 'supplement_mode': 'route_plan'}

    supplement = Supplement(**params)
    supplement.process()
    print("finished")