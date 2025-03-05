import os, json
import requests
from utils.coordinates import CoordinatesTransform


class TrajAcquisition:
    def __init__(self, key, origin, destination, way_points="", method_type="ors", other_params=None, save_path=""):
        self.key = key
        self.origin = origin
        self.destination = destination
        self.way_points = way_points
        self.method_type = method_type
        self.other_params = other_params
        self.save_path = save_path

        self.result_data = None

    def __check_input_params(self):
        # 根据method_type检查必填的参数
        if "ors" == self.method_type:
            pass

        if "amap" == self.method_type:
            # 对起终点进行检查：是否包含经纬度（不检查经度在前还是维度在前）
            coors = self.origin.split(',')
            if len(coors) != 2:
                raise Exception("The origin is incorrect, "
                                "Longitude first, latitude last, longitude and latitude are divided by ','")

            # 检查是否在国内：先进行坐标转换GCJ02-->WGS84
            lng, lat = CoordinatesTransform().gcj02_to_wgs84(*list(map(float, coors)))
            if not CoordinatesTransform().is_in_china(lng, lat):
                raise Exception("The origin is not in China")

            coors = self.destination.split(',')
            if len(coors) != 2:
                raise Exception("The destination is incorrect, "
                                "Longitude first, latitude last, longitude and latitude are divided by ','")

            lng, lat = CoordinatesTransform().gcj02_to_wgs84(*list(map(float, coors)))
            if not CoordinatesTransform().is_in_china(lng, lat):
                raise Exception("The destination is not in China")

        if "baidu" == self.method_type:
            # 纬度，经度
            pass
        pass

    def __acquire_traj_ors(self):
        pass

    def __acquire_traj_amap(self):
        url = 'https://restapi.amap.com/v5/direction/driving'
        params = {"key": self.key,
                  "origin": self.origin,
                  "destination": self.destination}
        # 更新参数
        if self.other_params is not None:
            params.update(self.other_params)

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
                    # print(coors_list)

                else:

                    print(response["info"])

        except Exception as e:
            print(e)

    def __acquire_traj_baidu(self):
        pass

    def __acquire_traj_process(self):
        # 根据method_type检查必填的参数
        if "ors" == self.method_type:
            pass

        if "amap" == self.method_type:
            self.__acquire_traj_amap()

        if "baidu" == self.method_type:
            pass
        pass

    def process(self):
        # 根据method_type检查参数
        self.__check_input_params()

        # 调用API或者库函数，获取轨迹点坐标
        self.__acquire_traj_process()

        # 保存轨迹信息
        # 保存为pd、geojson文件
        pass


if __name__ == '__main__':
    # 使用高德路径规划API获取轨迹
    key = "0ea6bc3a07caf07489fcd0b67f575c26"
    origin = "116.481028,39.989643"
    destination = "30.434446,39.90816"
    other_params = {"show_fields": "polyline"}
    traj_acquisition = TrajAcquisition(key=key, origin=origin, destination=destination,
                                       method_type="amap", other_params=other_params)
    # 使用百度路径规划API获取轨迹
    traj_acquisition.process()
    # 使用ORS库获取轨迹
    pass
