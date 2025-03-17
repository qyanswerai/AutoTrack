import os, json

import pandas as pd
import requests
from utils.coordinates import CoordinatesTransform
import openrouteservice as ors
from utils.config_parse import get_api_key
from traj_info_perfection import DrivingStateSimulate


class TrajAcquisition:
    def __init__(self, origin, destination, way_points="",
                 method_type="amap", coord_type="gcj02", other_params=None, save_path=""):
        self.raw_origin = origin
        self.raw_destination = destination
        self.raw_way_points = way_points
        self.method_type = method_type
        self.coord_type = coord_type
        self.other_params = other_params
        self.save_path = save_path

        self.coordinates = None
        self.profile = "driving-hgv"
        self.result_data = None

        self.alternative_methods = ["amap", "baidu", "ors"]

    def __check_input_params(self):
        # 对起终点进行检查：是否包含经纬度（不检查经度在前还是维度在前）
        if not isinstance(self.raw_origin, str) or len(self.raw_origin.split(',')) != 2:
            raise Exception("The origin is incorrect, "
                            "Longitude first, latitude last, longitude and latitude are divided by ','")

        if not isinstance(self.raw_destination, str) or len(self.raw_destination.split(',')) != 2:
            raise Exception("The destination is incorrect, "
                            "Longitude first, latitude last, longitude and latitude are divided by ','")

        # 检查坐标点是否在国内：先进行坐标转换gcj02/bd09ll-->wgs84
        if "wgs84" == self.coord_type:
            lng, lat = map(float, self.raw_origin.split(','))
            if not CoordinatesTransform().is_in_china(lng, lat):
                raise Exception("The origin is not in China")

            lng, lat = map(float, self.raw_destination.split(','))
            if not CoordinatesTransform().is_in_china(lng, lat):
                raise Exception("The origin is not in China")
        if "gcj02" == self.coord_type:
            lng, lat = CoordinatesTransform().gcj02_to_wgs84(*map(float, self.raw_origin.split(',')))
            if not CoordinatesTransform().is_in_china(lng, lat):
                raise Exception("The origin is not in China")

            lng, lat = CoordinatesTransform().gcj02_to_wgs84(*map(float, self.raw_destination.split(',')))
            if not CoordinatesTransform().is_in_china(lng, lat):
                raise Exception("The origin is not in China")
        if "bd09ll" == self.coord_type:
            lng, lat = CoordinatesTransform().gcj02_to_bd09(*map(float, self.raw_origin.split(',')))
            if not CoordinatesTransform().is_in_china(lng, lat):
                raise Exception("The origin is not in China")

            lng, lat = CoordinatesTransform().gcj02_to_wgs84(*map(float, self.raw_destination.split(',')))
            if not CoordinatesTransform().is_in_china(lng, lat):
                raise Exception("The origin is not in China")

        if self.coord_type not in ['wgs84', 'gcj02', 'bd09ll']:
            raise Exception(f"{self.coord_type} is not supported")

        if self.method_type not in ['ors', 'amap', 'baidu']:
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
        key = get_api_key('ors')
        client = ors.Client(key=key)

        # 更新参数，使用字典作为输入
        # if self.other_params is not None:
        #     params.update(self.other_params)

        try:
            route = client.directions(
                coordinates=self.coordinates,
                profile=self.profile,
                format="geojson"
            )
            coors_list = route["features"][0]["geometry"]["coordinates"]
            print(len(coors_list))
            self.result_data = coors_list
        except Exception as e:
            print('Failed to get shortest path using ORS')
            return None
        pass

    def __acquire_traj_amap(self):
        url = 'https://restapi.amap.com/v5/direction/driving'
        key = get_api_key('amap')
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
            print(e)

    def __acquire_traj_baidu(self):
        # 接口地址
        url = "https://api.map.baidu.com/direction/v2/driving"
        ak = get_api_key('baidu')

        params = {
            "origin": self.origin,
            "destination": self.destination,
            "ak": ak,
            "coord_type": self.coord_type}

        # 更新参数
        if self.way_points:
            params["waypoints"] = self.way_points

        # if self.other_params is not None:
        #     if "ret_coordtype" in self.other_params:
        #         params["ret_coordtype"] = self.other_params["ret_coordtype"]

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

        if self.result_data:
            self.result_data = pd.DataFrame(self.result_data, columns=['lng', 'lat'])

    def process(self):
        # 根据method_type检查参数
        self.__check_input_params()

        # 调用API或者库函数，获取轨迹点坐标
        self.__acquire_traj_process()

        # 获取timestamp、speed、direction
        driving_state_simulate = DrivingStateSimulate(self.result_data)
        driving_state_simulate.process()

        # 保存轨迹信息（保存为pd、geojson文件）


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
              "other_params": other_params
              }
    traj_acquisition = TrajAcquisition(**inputs)
    # 获取轨迹
    traj_acquisition.process()
    # 使用ORS库获取轨迹
    pass

