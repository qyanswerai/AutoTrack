import math
import os
import json
import pandas as pd
import geojson


def pd_to_geojson(data, data_info):
    if data is None:
        return None

    # 保存轨迹、起始点
    feature_list = []

    # 确定起点、终点信息（根据起止轨迹点确定）
    start_point = data[["lng", "lat", "timestamp"]].iloc[0].to_dict()
    end_point = data[["lng", "lat", "timestamp"]].iloc[-1].to_dict()
    start_time = data_info["start_time"]
    end_time = data_info["end_time"]
    start_point["timestamp"] = start_time
    end_point["timestamp"] = end_time

    sp = geojson.Feature(
        geometry=geojson.Point(tuple(data[["lng", "lat"]].iloc[0])),
        properties={"color": "green",
                    "time": start_time,
                    "point": start_point,
                    "popup": {"title": "起点"}})

    ep = geojson.Feature(
        geometry=geojson.Point(tuple(data[["lng", "lat"]].iloc[-1])),
        properties={"color": "red",
                    "time": end_time,
                    "point": end_point,
                    "popup": {"title": "终点"}})

    feature_list.append(sp)
    feature_list.append(ep)

    properties = {"color": "green",
                  "start_time": start_time,
                  "end_time": end_time,
                  "start_point": start_point,
                  "end_point": end_point,
                  "timestamps": data["timestamp"].values.tolist(),
                  "speeds": data["speed"].values.tolist(),
                  "directions": data["direction"].values.tolist()}

    coordinates = data[["lng","lat"]].values.tolist()
    line = geojson.Feature(
        geometry=geojson.LineString(coordinates),
        properties=properties)
    feature_list.append(line)

    feature_collection = geojson.FeatureCollection(features=feature_list, meta=data_info)

    return feature_collection


def save_data(data, data_info=None, save_path="", file_name="default_name"):
    # 是否保存处理后的轨迹
    if data is not None and save_path != "":
        if file_name == "default_name":
            file_name = '_'.join([data_info["task_id"], data_info["start_center_name"],
                                  data_info["end_center_name"], data_info["plate_num"]]) + '.json'
        path = os.path.join(save_path, file_name)
        with open(path, 'w', encoding='utf-8') as f:
            # 使用json.dump()方法将feature_collection对象写入文件
            json.dump(data, f, ensure_ascii=False, indent=4)


def cal_haversine_dis(cur_point, next_point):
    AVG_EARTH_RADIUS = 6371.0088  # in kilometers

    lng1, lat1 = cur_point
    lng2, lat2 = next_point
    # 转换为弧度
    lng1_rad, lat1_rad, lng2_rad, lat2_rad = map(math.radians, [lng1, lat1, lng2, lat2])

    d_lng = lng2_rad - lng1_rad
    d_lat = lat2_rad - lat1_rad
    d = math.sin(d_lat * 0.5) ** 2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(d_lng * 0.5) ** 2
    d = 2 * AVG_EARTH_RADIUS * math.asin(math.sqrt(d))  # in kilometers
    return d * 1000


def cal_bearing(lng1, lat1, lng2, lat2):
    # 将经纬度从度转换为弧度
    lng1_rad, lat1_rad, lng2_rad, lat2_rad = map(math.radians, [lng1, lat1, lng2, lat2])

    # 计算经度差
    delta_lon = lng2_rad - lng1_rad

    # 计算方位角的 y 和 x 分量
    y = math.sin(delta_lon) * math.cos(lat2_rad)
    x = math.cos(lat1_rad) * math.sin(lat2_rad) - math.sin(lat1_rad) * math.cos(lat2_rad) * math.cos(delta_lon)

    # 计算方位角的弧度值
    initial_bearing = math.atan2(y, x)

    # 将弧度转换为角度，并确保在 0 到 360 度之间
    initial_bearing_degrees = math.degrees(initial_bearing)
    bearing = (initial_bearing_degrees + 360) % 360

    return bearing


def split_segment(l):
    left = right = 0
    segment = []
    while right < len(l) - 1:
        if l[right + 1] == l[right] + 1:
            right += 1
        else:
            if right > left:
                segment.append(l[left:right + 1])
            left = right + 1
            right = right + 1
    if right > left:
        segment.append(l[left:right + 1])
    return segment


if __name__ == '__main__':
    # 示例：计算两个点之间的方位角
    lat1, lon1 = 39.9042, 116.4074  # 北京
    # lat2, lon2 = 39.9042, 116.4074  # 北京
    lat2, lon2 = 31.2304, 121.4737  # 上海

    bearing = cal_bearing(lon1, lat1, lon2, lat2)
    print(bearing)
    # print(f"两点之间的连线与正北方向的夹角为: {bearing:.2f} 度")

    d = cal_haversine_dis([lon1, lat1], [lon2, lat2])
    print(d)