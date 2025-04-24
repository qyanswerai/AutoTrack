import math
import os
import json
import geojson
import time
import numpy as np
import pandas as pd

from utils.coordinates import CoordinatesTransform


def pd_to_geojson(data, data_info):
    # 保存轨迹、起始点
    feature_list = []

    # 确定起点、终点信息（根据起止轨迹点确定）
    start_point = data[["lng", "lat", "timestamp"]].iloc[0].to_dict()
    end_point = data[["lng", "lat", "timestamp"]].iloc[-1].to_dict()
    # Object of type int64 is not JSON serializable，可以转换为str（简单的处理方式）
    # 或者转换为时间：pd.Timestamp(data['timestamp'].iloc[0],unit='ms',tz='Asia/Shanghai')
    #     1402099200000 ==> Timestamp('2014-06-07 08:00:00+0800', tz='Asia/Shanghai')
    start_time = str(data["timestamp"].iloc[0])
    end_time = str(data["timestamp"].iloc[-1])
    start_point["timestamp"] = start_time
    end_point["timestamp"] = end_time

    data_info["start_point"] = start_point
    data_info["end_point"] = end_point
    data_info["start_time"] = start_time
    data_info["end_time"] = end_time

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

    coordinates = data[["lng", "lat"]].values.tolist()
    line = geojson.Feature(
        geometry=geojson.LineString(coordinates),
        properties=properties)
    feature_list.append(line)

    feature_collection = geojson.FeatureCollection(features=feature_list, meta=data_info)

    return feature_collection


def save_data(data, data_info=None, save_path="", file_name="", save_type="csv"):
    # 是否保存处理后的轨迹
    if data is not None and save_path != "":
        if file_name == "":
            file_name = str(int(time.time() * 1000))
            file_path = os.path.join(save_path, file_name + '.' + save_type)
        else:
            file_path = os.path.join(save_path, file_name + '.' + save_type)

        if save_type == "json":
            with open(file_path, 'w', encoding='utf-8') as f:
                # 保存data_info为json对象
                json.dump(data_info, f, ensure_ascii=False, indent=4)
        else:
            data.to_csv(file_path, index=False)

        # 单独保存一份geojson格式的json文件
        file_path = os.path.join(save_path, file_name + '_geojson.json')
        with open(file_path, 'w', encoding='utf-8') as f:
            data_info = data_info.copy()
            # traj_points不放在geojson文件的meta字段中
            data_info.pop('traj_points')

            json_data = pd_to_geojson(data, data_info)
            # 使用json.dump()方法将feature_collection对象写入文件
            json.dump(json_data, f, ensure_ascii=False, indent=4)


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


def cal_haversine_dis_vector(df):
    """
    向量化计算相邻点之间的球面距离（单位：km）
    """
    AVG_EARTH_RADIUS = 6371.0088  # in kilometers
    # 将角度转换为弧度
    # lon1 = np.radians(df['lng'].iloc[:-1])
    # lat1 = np.radians(df['lat'].iloc[:-1])
    # lon2 = np.radians(df['lng'].iloc[1:])
    # lat2 = np.radians(df['lat'].iloc[1:])

    # 计算经纬度差值
    # 注意：lon1是Series，使用 pandas Series 直接相减时，索引会自动对齐
    # dlon = lon2 - lon1
    # dlat = lat2 - lat1

    # 确保数据按位置顺序处理（忽略原始索引）
    lon = np.radians(df['lng'].values)
    lat = np.radians(df['lat'].values)
    # 直接使用数组切片计算相邻差值（避免索引对齐问题）
    dlon = lon[1:] - lon[:-1]
    dlat = lat[1:] - lat[:-1]

    # Haversine 公式
    a = np.sin(dlat / 2) ** 2 + np.cos(lat[:-1]) * np.cos(lat[1:]) * np.sin(dlon / 2) ** 2
    c = 2 * np.arcsin(np.sqrt(a))

    # 计算距离
    distance = AVG_EARTH_RADIUS * c
    return distance * 1000


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


def cal_direction(data):
    data[['lng_up', 'lat_up']] = data[['lng', 'lat']].shift(1)
    data[['lng_up', 'lat_up']] = data[['lng_up', 'lat_up']].bfill()
    data['direction'] = data.apply(
        lambda row: cal_bearing(row['lng_up'], row['lat_up'], row['lng'], row['lat']), axis=1)

    # 用第2个点的方向角作为第1个点的方向角
    data.loc[0, 'direction'] = data.loc[1, 'direction']
    data.drop(columns=['lng_up', 'lat_up'], inplace=True)

    raw_coordinates = data[['lng', 'lat']].values.tolist()
    # 若相邻轨迹点经纬度相同，则cal_bearing计算得到的航向角为0，使用两侧的轨迹点坐标重新计算航向角
    # 记录坐标相同的轨迹点
    i = 0
    stay_points = []
    while i < len(raw_coordinates) - 1:
        if raw_coordinates[i] == raw_coordinates[i + 1]:
            stay_points.extend([i, i + 1])
        i += 1

    stay_segments = split_segment(sorted(set(stay_points)))

    # 更新航向角
    for stay_segment in stay_segments:
        up_point = raw_coordinates[max(0, stay_segment[0] - 1)]
        down_point = raw_coordinates[min(len(raw_coordinates) - 1, stay_segment[-1] + 1)]
        direction = cal_bearing(*up_point, *down_point)
        data.loc[stay_segment, 'direction'] = direction


def update_pd_data(data, from_crs="GCJ02", to_crs="WGS84"):
    coord_list = CoordinatesTransform().coord_transform(data[['lng', 'lat']].values.tolist(), from_crs, to_crs, 'list')
    coord_data = pd.DataFrame(coord_list, columns=['lng_transformed', 'lat_transformed'])
    result = pd.concat([data, coord_data], axis=1)
    # 删除原有的坐标列，新增WGS84坐标列（命名为lng、lat）
    result.drop(columns=["lng", "lat"], inplace=True)
    result.rename(columns={"lng_transformed": "lng", "lat_transformed": "lat"}, inplace=True)
    return result


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