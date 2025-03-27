import os, json

import pandas as pd
import requests
import openrouteservice as ors
from pydantic import BaseModel, ValidationError
from pyproj import CRS, Transformer
from shapely.geometry import Point, LineString
from utils.coordinates import CoordinatesTransform
from utils.config_parse import get_api_key
from utils.basic_utils import save_data
from traj_acquisition.traj_info_perfection import DrivingStateSimulate


class TrajAcquisitionItem(BaseModel):
    # 对于base_data、raw_data，仅校验其是否存在，后续在TrajectoryCompare初始化时根据data_type进行字段校验
    origin: str
    destination: str
    way_points: str = ""
    method_type: str = "amap"
    coord_type: str = "gcj02"
    other_params: dict = None
    interpolate_flag: bool = False
    save_path: str = ""
    save_name: str = ""
    result_type: str = "csv"
    logger: object = None


class TrajAcquisition:
    def __init__(self, origin, destination, way_points="",
                 method_type="amap", coord_type="gcj02", other_params=None, interpolate_flag=False,
                 save_path="", save_name="", result_type="csv", logger=None):
        self.raw_origin = origin
        self.raw_destination = destination
        self.raw_way_points = way_points
        self.method_type = method_type
        self.coord_type = coord_type
        self.other_params = other_params
        self.interpolate_flag = interpolate_flag
        self.save_path = save_path
        self.save_name = save_name
        self.result_type = result_type
        self.logger = logger

        self.coordinates = None
        self.result_data = None

        self.data_info = {"origin": self.raw_origin, "destination": self.raw_destination, "way_points": self.raw_way_points}

        self.alternative_methods = ["amap", "baidu", "ors"]

    def __check_input_params(self):
        # 对起终点进行检查：是否包含经纬度（不检查经度在前还是维度在前）
        if not isinstance(self.raw_origin, str) or len(self.raw_origin.split(',')) != 2:
            self.logger.error("The origin is incorrect, longitude and latitude should be divided by ','")
            raise Exception("The origin is incorrect, "
                            "Longitude first, latitude last, longitude and latitude are divided by ','")

        if not isinstance(self.raw_destination, str) or len(self.raw_destination.split(',')) != 2:
            self.logger.error("The destination is incorrect, longitude and latitude should be divided by ','")
            raise Exception("The destination is incorrect, longitude and latitude should be divided by ','")

        # 检查坐标点是否在国内：先进行坐标转换gcj02/bd09ll-->wgs84
        in_china = True
        if "wgs84" == self.coord_type:
            lng, lat = map(float, self.raw_origin.split(','))
            if not CoordinatesTransform().is_in_china(lng, lat):
                in_china = False
            lng, lat = map(float, self.raw_destination.split(','))
            if not CoordinatesTransform().is_in_china(lng, lat):
                in_china = False
        if "gcj02" == self.coord_type:
            lng, lat = CoordinatesTransform().gcj02_to_wgs84(*map(float, self.raw_origin.split(',')))
            if not CoordinatesTransform().is_in_china(lng, lat):
                in_china = False
            lng, lat = CoordinatesTransform().gcj02_to_wgs84(*map(float, self.raw_destination.split(',')))
            if not CoordinatesTransform().is_in_china(lng, lat):
                in_china = False
        if "bd09ll" == self.coord_type:
            lng, lat = CoordinatesTransform().bd09_to_wgs84(*map(float, self.raw_origin.split(',')))
            if not CoordinatesTransform().is_in_china(lng, lat):
                in_china = False
            lng, lat = CoordinatesTransform().bd09_to_wgs84(*map(float, self.raw_destination.split(',')))
            if not CoordinatesTransform().is_in_china(lng, lat):
                in_china = False

        if not in_china:
            # 若不在国内，则使用ORS方法
            self.method_type = 'ors'
            self.alternative_methods = ['ors']
            self.logger.warning("The origin or destination is not in China, only ors method available")
            # raise Exception("The origin is not in China")

        if self.coord_type not in ['wgs84', 'gcj02', 'bd09ll']:
            self.logger.error(f"{self.coord_type} is not supported")
            raise Exception(f"{self.coord_type} is not supported")

        if self.method_type not in ['ors', 'amap', 'baidu']:
            self.logger.error(f"{self.method_type} is not supported")
            raise Exception(f"{self.method_type} is not supported")

    def __transform_input_coord(self):
        # 检查method_type与coord_type是否匹配，否则进行坐标转换
        # 将origin、destination、way_points转换为与method_type匹配的形式
        if "ors" == self.method_type:
            if 'wgs84' == self.coord_type:
                # 调整起点、终点、中间点的形式
                # 起终点：纬度，经度
                # 中间点：纬度，经度|纬度，经度
                self.origin = list(map(float, self.raw_origin.split(',')))
                self.destination = list(map(float, self.raw_destination.split(',')))
                if self.raw_way_points:
                    self.way_points = [list(map(float, p.split(','))) for p in self.raw_way_points.split(';')]
                    self.coordinates = [self.origin, *self.way_points, self.destination]
                else:
                    self.coordinates = [self.origin, self.destination]
            else:
                self.origin = CoordinatesTransform().coord_transform(self.raw_origin, self.coord_type, 'wgs84')
                self.destination = CoordinatesTransform().coord_transform(self.raw_destination, self.coord_type, 'wgs84')
                if self.raw_way_points:
                    self.way_points = CoordinatesTransform().coord_transform(self.raw_way_points, self.coord_type, 'wgs84')
                    self.coordinates = [*self.origin, *self.way_points, *self.destination]
                else:
                    self.coordinates = [*self.origin, *self.destination]

        if "amap" == self.method_type:
            if 'gcj02' == self.coord_type:
                self.origin = self.raw_origin
                self.destination = self.raw_destination
                self.way_points = self.raw_way_points
            else:
                self.origin = CoordinatesTransform().coord_transform(self.raw_origin, self.coord_type, 'gcj02')
                self.origin = ','.join(map(str, self.origin[0]))
                self.destination = CoordinatesTransform().coord_transform(self.raw_destination, self.coord_type, 'gcj02')
                self.destination = ','.join(map(str, self.destination[0]))
                if self.raw_way_points:
                    self.way_points = CoordinatesTransform().coord_transform(self.raw_way_points, self.coord_type, 'gcj02')
                    self.way_points = ';'.join([','.join(map(str, p)) for p in self.way_points])
                else:
                    self.way_points = ""

        if "baidu" == self.method_type:
            if 'bd09ll' == self.coord_type:
                # 调整起点、终点、中间点的形式
                # 起终点：纬度，经度
                # 中间点：纬度，经度|纬度，经度
                self.origin = ','.join(self.raw_origin.split(',')[::-1])
                self.destination = ','.join(self.raw_destination.split(',')[::-1])
                if self.raw_way_points:
                    self.way_points = '|'.join([','.join(p.split(',')[::-1]) for p in self.raw_way_points.split(';')])
                else:
                    self.way_points = ""
            else:
                self.origin = CoordinatesTransform().coord_transform(self.raw_origin, self.coord_type, 'bd09ll')
                self.origin = ','.join(map(str, self.origin[0][::-1]))
                self.destination = CoordinatesTransform().coord_transform(self.raw_destination, self.coord_type, 'bd09ll')
                self.destination = ','.join(map(str, self.destination[0][::-1]))
                if self.raw_way_points:
                    self.way_points = CoordinatesTransform().coord_transform(self.raw_way_points, self.coord_type, 'bd09ll')
                    self.way_points = '|'.join([','.join(map(str, p[::-1])) for p in self.way_points])
                else:
                    self.way_points = ""

    def __acquire_traj_ors(self):
        # 调用direction函数确定两点之间的最短路
        key = get_api_key(method='ors')
        client = ors.Client(key=key)

        params = {"coordinates": self.coordinates}
        # 更新参数，使用字典作为输入
        if self.other_params is not None:
            for param in ['profile', 'format']:
                if param in self.other_params:
                    params[param] = self.other_params[param]

        try:
            route = client.directions(**params)
            coors_list = route["features"][0]["geometry"]["coordinates"]
            print(len(coors_list))
            self.result_data = coors_list
        except Exception as e:
            print('Failed to get shortest path using ORS')
            self.logger.error(f'Failed to get shortest path using ORS: {e}')
            raise Exception(e)

    def __acquire_traj_amap(self):
        url = 'https://restapi.amap.com/v5/direction/driving'
        key = get_api_key(method='amap')
        params = {"key": key,
                  "origin": self.origin,
                  "destination": self.destination}

        # 更新参数
        if self.way_points:
            params["waypoints"] = self.way_points

        if self.other_params is not None:
            if "show_fields" in self.other_params:
                params["show_fields"] = self.other_params["show_fields"]

        try:
            response = requests.get(url=url, params=params)
            if response.status_code == 200:
                response = response.json()
                coors_list = []
                if response["infocode"] == "10000":
                    # 暂时不对response中的字段进行检查
                    paths = response["route"]["paths"]
                    for path in paths:
                        steps = path["steps"]
                        for step in steps:
                            coors_list.extend(step["polyline"].split(';'))
                    coors_list = [list(map(float, coord.split(','))) for coord in coors_list]
                    print(len(coors_list))
                    self.result_data = coors_list
                else:
                    print(response["info"])

        except Exception as e:
            print('Failed to get shortest path using amap')
            self.logger.error(f'Failed to get shortest path using amap: {e}')
            raise Exception(e)

    def __acquire_traj_baidu(self):
        # 接口地址
        url = "https://api.map.baidu.com/direction/v2/driving"
        ak = get_api_key(method='baidu')

        params = {
            "origin": self.origin,
            "destination": self.destination,
            "ak": ak,
            "coord_type": self.coord_type}

        # 更新参数
        if self.way_points:
            params["waypoints"] = self.way_points

        try:
            response = requests.get(url=url, params=params)
            if response.status_code == 200:
                response = response.json()
                coors_list = []
                for route in response['result']['routes']:
                    for step in route['steps']:
                        coors_list.extend(step['path'].split(';'))
                coors_list = [list(map(float, coord.split(','))) for coord in coors_list]
                print(len(coors_list))
                self.result_data = coors_list
        except Exception as e:
            print('Failed to get shortest path using baidu')
            self.logger.error(f'Failed to get shortest path using baidu: {e}')
            raise Exception(e)

    def __enhance_by_interpolate(self):
        # 坐标系转换
        coords = CoordinatesTransform().coord_transform(self.result_data.values.tolist(), self.coord_type, 'wgs84', 'list')

        # 指定采样间距
        sample_interval = 100
        from_crs = CRS('EPSG: 4326')
        to_crs = CRS('EPSG: 32648')

        trans_4326 = Transformer.from_crs(from_crs, to_crs, always_xy=True)
        trans_32648 = Transformer.from_crs(to_crs, from_crs, always_xy=True)

        # 地理坐标系转换为投影坐标系
        points_utm = [trans_4326.transform(lng, lat) for lng, lat in coords]
        line_utm = LineString(points_utm)
        # 给result_data新增distance列
        distance_list = [line_utm.project(Point(point)) for point in points_utm]
        self.result_data['distance'] = distance_list

        resample_data = pd.DataFrame()
        total_length = line_utm.length
        distance_list = [i * sample_interval for i in range(int(total_length / sample_interval))]
        points_utm = [line_utm.interpolate(distance) for distance in distance_list]
        points_wgs84 = [trans_32648.transform(point.x, point.y) for point in points_utm]
        # 坐标系转换
        coords = CoordinatesTransform().coord_transform(points_wgs84, 'wgs84', self.coord_type, 'list')
        resample_data[['lng', 'lat']] = coords
        resample_data['distance'] = distance_list
        # 指定node_type
        # resample_data['node_type'] = 'resample'

        self.result_data = pd.concat([self.result_data, resample_data], ignore_index=True)

        self.result_data.sort_values(by='distance', inplace=True)
        self.result_data.drop_duplicates(subset='distance', keep='first', inplace=True)
        self.result_data.reset_index(drop=True, inplace=True)
        self.result_data.drop(columns='distance', inplace=True)

    def __acquire_traj_process(self):
        # 先调用给定的method，若失败则自动调用其他API
        self.alternative_methods.remove(self.method_type)
        self.alternative_methods.insert(0, self.method_type)

        while self.result_data is None and len(self.alternative_methods) > 0:
            self.method_type = self.alternative_methods.pop(0)
            self.__transform_input_coord()
            # 根据method_type检查必填的参数
            if "ors" == self.method_type:
                self.__acquire_traj_ors()

            if "amap" == self.method_type:
                self.__acquire_traj_amap()

            if "baidu" == self.method_type:
                self.__acquire_traj_baidu()

        self.data_info["method_type"] = self.method_type
        self.data_info["coord_type"] = self.coord_type
        self.logger.info(f"method type: {self.method_type}")
        self.logger.info(f"coord type: {self.coord_type}")

        if self.result_data:
            self.result_data = pd.DataFrame(self.result_data, columns=['lng', 'lat'])
            if self.interpolate_flag:
                # 插值前需要先将坐标系转换为WGS84
                self.__enhance_by_interpolate()

            # 获取timestamp、speed、direction
            driving_state_simulate = DrivingStateSimulate(self.result_data)
            self.result_data = driving_state_simulate.process()

    def process(self):
        try:
            # 根据method_type检查参数
            self.__check_input_params()
            self.logger.info("input params has been checked")

            # 调用API或者库函数，获取轨迹点坐标
            self.__acquire_traj_process()
            self.logger.info("trajectory has been acquired successfully")

            if not self.result_data.empty:
                # 保存轨迹信息（保存为pd、geojson文件）
                save_data(self.result_data, self.data_info, self.save_path, self.save_name, self.result_type)
        except Exception as e:
            print(f"trajectory acquisition has failed: {e}")
            self.logger.error(f"trajectory acquisition has failed: {e}")

        return self.result_data


if __name__ == '__main__':
    # 起点、终点、中间点的形式符合高德驾车路径规划API的要求
    origin = "116.481028,39.989643"
    destination = "116.434446,39.90816"
    way_points = "116.461028,39.959643;116.441028,39.929643"
    other_params = {"show_fields": "polyline"}
    inputs = {"origin": origin,
              "destination": destination,
              # "way_points": way_points,
              "method_type": "amap",
              # "coord_type": "bd09ll",
              "other_params": other_params,
              }
    try:
        TrajAcquisitionItem(**inputs)
        traj_acquisition = TrajAcquisition(**inputs)
        traj_acquisition.process()
    except ValidationError as e:
        print(e)

