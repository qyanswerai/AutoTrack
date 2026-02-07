import math
import os
import json
import geojson
import time
import numpy as np
import pandas as pd

from utils.coordinates import CoordinatesTransform


def split_segment(l):
    """
    列表划分为子列表：例如[1,2,3,5,7,8,10]==>[[1,2,3],[7,8]]
    :param l: 列表（或者数组）
    :return: 划分后的列表
    """
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


def cal_haversine_dis(cur_point, next_point):
    """
    采用haversine公式，根据坐标计算距离
    :param cur_point: 点的坐标
    :param next_point: 另一个点的坐标
    :return: 距离（单位：m）
    """
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
    向量化计算相邻点之间的球面距离（单位：m），返回距离数组
    :param df: 轨迹数据，要求有lng、lat列（用于计算距离）
    :return: 距离数组
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
    """
    根据坐标计算航向角（两点连线的角度）
    :param lng1: 上游轨迹点经度
    :param lat1: 上游轨迹点纬度
    :param lng2: 下游轨迹点经度
    :param lat2: 下游轨迹点纬度
    :return: 航向角
    """
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


def cal_direction(data):
    """
    对于轨迹数据，计算或者更新航向角
    :param data: 轨迹数据（要求有lng、lat列）
    :return: 更新后的轨迹数据
    """
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


def update_direction(data):
    """
    生成（根据经纬度计算）、更新轨迹点的航向角
    :param data: 轨迹数据
    :return: 更新后的轨迹数据
    """
    data["lng_up"] = data["lng"].shift(1)
    data["lat_up"] = data["lat"].shift(1)
    data[["lng_up", "lat_up"]] = data[["lng_up", "lat_up"]].bfill()
    data["direction"] = data.apply(
        lambda row: cal_bearing(row["lng_up"], row["lat_up"], row["lng"], row["lat"]),
        axis=1,
    )

    # 用第2个点的方向角作为第1个点的方向角
    data.loc[0, "direction"] = data.loc[1, "direction"]
    data.drop(columns=["lng_up", "lat_up"], inplace=True)

    raw_coordinates = data[["lng", "lat"]].values.tolist()
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
        down_point = raw_coordinates[
            min(len(raw_coordinates) - 1, stay_segment[-1] + 1)
        ]
        direction = cal_bearing(*up_point, *down_point)
        data.loc[stay_segment, "direction"] = direction
    return data


def update_speed(data):
    """
    生成（根据经纬度计算）、更新轨迹点的速度
    :param data: 轨迹数据
    :return: 更新后的轨迹数据
    """
    distances = cal_haversine_dis_vector(data)
    timestamps = data["timestamp"].values / 1000
    # 计算速度，m/s转换为km/h
    speeds = distances / (timestamps[1:] - timestamps[:-1]) * 3.6
    speeds = speeds.round(2)
    # 速度合理性调整：高于150km/h的轨迹点，设置为150km/h
    speeds[speeds > 150] = 150

    # 直接指定最后一个轨迹点的速度值
    speeds = np.append(speeds, speeds[-1])
    data['speed'] = speeds
    return data


def update_pd_data(data, from_crs="gcj02", to_crs="wgs84"):
    """
    更新轨迹数据：对经纬度坐标进行坐标系转换
    :param data: 轨迹数据
    :param from_crs: 现状坐标系
    :param to_crs: 目标坐标系
    :return: 坐标转换后的轨迹数据
    """
    coord_list = CoordinatesTransform().coord_transform(data[['lng', 'lat']].values.tolist(), from_crs, to_crs, 'list')
    coord_data = pd.DataFrame(coord_list, columns=['lng_transformed', 'lat_transformed'])
    result = pd.concat([data, coord_data], axis=1)
    # 删除原有的坐标列，新增WGS84坐标列（命名为lng、lat）
    result.drop(columns=["lng", "lat"], inplace=True)
    result.rename(columns={"lng_transformed": "lng", "lat_transformed": "lat"}, inplace=True)
    return result

def read_track_data(path, data_info=None):
    """
    根据文件路径读取轨迹
    :param path: 轨迹文件路径
    :param data_info: 轨迹信息
    :return: geojson格式的轨迹数据
    """
    # base_name = os.path.basename(path)
    # 解析文件，并确定coord_type
    if path.endswith("json"):
        with open(path, encoding='utf-8') as f:
            data = json.load(f)

        if "type" in data and data["type"] == "FeatureCollection":
            return data
        else:
            print("轨迹数据为json格式，但不符合geojson的字段标准")
            raise Exception('轨迹数据为json格式时，需要符合geojson的字段标准')

    elif path.endswith("csv"):
        data = pd.read_csv(path)
        if data_info is None:
            data_info = {}
        return pd_to_geojson(data, data_info)
    else:
        raise Exception("暂不支持该类轨迹文件，请转换为json或csv格式")


def examine_and_update_raw_data(data):
    """
    # 检查轨迹数据的字段是否齐全：lng、lat、timestamp、speed、direction
    若缺少lng、lat、timestamp则报错；若缺少speed、direction则根据经纬度生成
    :param data: 轨迹数据
    :return: 轨迹数据是否可用，轨迹数据，关键信息
    """

    missing_fields = {"lng", "lat", "timestamp", "speed", "direction"} - set(data.columns)
    key_msg = ''
    available_flag = True
    if missing_fields:
        if "lng" in missing_fields or "lat" in missing_fields or "timestamp" in missing_fields:
            key_msg = f"轨迹数据缺少必要的字段：{missing_fields}。"
            available_flag = False
            return available_flag, data, key_msg

        # 若轨迹无direction字段，则重新计算direction
        if "direction" in missing_fields:
            key_msg += "轨迹数据航向角不可用，重新生成。"
            data = update_direction(data)
        # 若轨迹无speed字段，则重新计算speed
        if "speed" in missing_fields:
            key_msg += "轨迹数据速度不可用，重新生成。"
            data = update_speed(data)

        return available_flag, data, key_msg

    # 若不足20个轨迹点，直接返回
    if len(data) < 20:
        key_msg += f"仅{len(data)}个轨迹点，可能会影响算法效果。"

    # 检查是否包含空值
    if data.isnull().values.any():
        key_msg += "部分轨迹点缺少必要的字段，删除此类点。"
        # 删除空值所在的行
        data = data.dropna()

    # 类型转换
    data["lng"] = data["lng"].astype(float)
    data["lat"] = data["lat"].astype(float)
    data["timestamp"] = data["timestamp"].astype("int64")
    data["speed"] = data["speed"].astype(float)
    data["direction"] = data["direction"].astype(float)

    # 对timestamp排序并去重
    data.sort_values(by=["timestamp"], inplace=True)
    data.drop_duplicates(subset="timestamp", keep="first", inplace=True)
    data.reset_index(drop=True, inplace=True)

    return available_flag, data, key_msg


def pd_to_geojson(data, data_info):
    """
    dataframe转换为geojson
    :param data: dataframe格式的轨迹数据
    :param data_info: 轨迹数据相关信息，例如起终点
    :return: geojson格式的轨迹数据
    """
    # 保存轨迹、起始点
    feature_list = []

    # 确定起点、终点信息（根据起止轨迹点确定）
    start_point = data[["lng", "lat"]].iloc[0].to_dict()
    end_point = data[["lng", "lat"]].iloc[-1].to_dict()
    data_info["start_point"] = start_point
    data_info["end_point"] = end_point
    # Object of type int64 is not JSON serializable，可以转换为str（简单的处理方式）
    # 或者转换为时间：pd.Timestamp(data['timestamp'].iloc[0],unit='ms',tz='Asia/Shanghai')
    #     1402099200000 ==> Timestamp('2014-06-07 08:00:00+0800', tz='Asia/Shanghai')
    sp_properties = {"color": "green",
                     "point": start_point,
                     "popup": {"title": "起点"}}
    ep_properties = {"color": "red",
                     "point": end_point,
                     "popup": {"title": "终点"}}

    properties = {"color": "green",
                  "start_point": start_point,
                  "end_point": end_point}

    if 'timestamp' in data:
        start_time = str(data["timestamp"].iloc[0])
        end_time = str(data["timestamp"].iloc[-1])

        data_info["start_time"] = start_time
        data_info["end_time"] = end_time

        sp_properties["time"] = start_time
        ep_properties["time"] = end_time

        properties["start_time"] = start_time
        properties["end_time"] = end_time
        properties["timestamps"] = data["timestamp"].values.tolist()
    if "speed" in data:
        properties["speeds"] = data["speed"].values.tolist()
    if "direction" in data:
        properties["directions"] = data["direction"].values.tolist()

    sp = geojson.Feature(
        geometry=geojson.Point(tuple(data[["lng", "lat"]].iloc[0])),
        properties=sp_properties)

    ep = geojson.Feature(
        geometry=geojson.Point(tuple(data[["lng", "lat"]].iloc[-1])),
        properties=ep_properties)

    feature_list.append(sp)
    feature_list.append(ep)

    coordinates = data[["lng", "lat"]].values.tolist()
    line = geojson.Feature(
        geometry=geojson.LineString(coordinates),
        properties=properties)
    feature_list.append(line)

    feature_collection = geojson.FeatureCollection(features=feature_list, meta=data_info)

    return feature_collection

def geojson_to_pd(data):
    """
    geojson转换为dataframe
    :param data: dataframe格式的轨迹数据
    :return: geojson格式的轨迹数据、经纬度坐标数据
    """
    pd_data = None
    coordinates = None
    for feature in data["features"]:
        if feature["geometry"]["type"] == "LineString":
            coordinates = np.array(feature["geometry"]["coordinates"])
            pd_data = pd.DataFrame(coordinates, columns=["lng", "lat"])

            if 'timestamps' in feature['properties']:
                pd_data['timestamp'] = feature['properties']['timestamps']
            if 'directions' in feature['properties']:
                pd_data['direction'] = feature['properties']['directions']
            if 'speeds' in feature['properties']:
                pd_data['speed'] = feature['properties']['speeds']
    return pd_data, coordinates


def save_data(data, data_info=None, save_path=""):
    """
    保存轨迹数据
    :param data: 轨迹数据
    :param data_info: 轨迹数据相关信息
    :param save_path: 保存路径
    :return:
    """
    json_data = None
    if data is not None:
        # 使用generate_info（meta字段的一个子属性）记录轨迹生成相关的信息
        data_info = {"generate_info": data_info}
        json_data = pd_to_geojson(data, data_info)

    # 是否保存处理后的轨迹
    if data is not None and save_path != "":
        if not (save_path.endswith(".json") or save_path.endswith(".csv")):
            # 若save_path为文件夹，则使用时间戳作为文件名
            # 默认保存为geojson格式的json文件
            if not os.path.exists(save_path):
                os.makedirs(save_path)
            file_name = str(int(time.time() * 1000)) + '.json'
            save_path = os.path.join(save_path, file_name)

        if save_path.endswith(".json"):
            # 保存为geojson格式的json文件
            with open(save_path, 'w', encoding='utf-8') as f:
                # 使用json.dump()方法将feature_collection对象写入文件
                json.dump(json_data, f, ensure_ascii=False, indent=4)
        else:
            data.to_csv(save_path, index=False)

    return json_data


def get_noise_info(data, denoising_level='low'):
    """
    获取噪点信息
    :param data: 轨迹数据
    :param denoising_level: 降噪等级
    :return: 噪点信息、噪点索引
    """
    denoising_limit_info = {
        "low": {"distance_limit": 10000, "time_limit": 3},
        "mid": {"distance_limit": 8000, "time_limit": 2},
        "high": {"distance_limit": 5000, "time_limit": 1},
    }
    noise_info = {"noise_section_num": 0, "max_noise_section_length": 0, "sum_noise_section_length": 0,
                  "mean_noise_section_length": 0,
                  "noise_num": 0, "noise_points": []}

    distance_limit = denoising_limit_info[denoising_level]["distance_limit"]
    time_limit = denoising_limit_info[denoising_level]["time_limit"]

    coordinates = data[['lng', 'lat']].values
    # 向量化计算距离
    distances = cal_haversine_dis_vector(data)
    # Step1：根据距离阈值确定噪点（初筛），记录轨迹点索引、距离
    detected_noise_segments = np.where(distances >= distance_limit)[0]
    segment_dis_list = distances[detected_noise_segments]


    if len(detected_noise_segments) <= 1:
        print("未识别到噪点")
        return noise_info, []

    # 调整为轨迹点对：列表表达式；广播机制 + 按列堆叠
    detected_noise_segments = np.column_stack((detected_noise_segments, detected_noise_segments + 1))

    noise_info["noise_section_num"] = len(detected_noise_segments)
    noise_info["max_noise_section_length"] = round(segment_dis_list.max() / 1000, 3)
    noise_info["sum_noise_section_length"] = round(segment_dis_list.sum() / 1000, 3)
    noise_info["mean_noise_section_length"] = round(segment_dis_list.mean() / 1000, 3)

    # Step2：根据相邻的noise_segment，判断要剔除的噪点
    # 记录要剔除的轨迹点
    noise_list = []
    for i in range(len(detected_noise_segments) - 1):
        left_index = detected_noise_segments[i][0]
        right_index = detected_noise_segments[i + 1][1]
        cur_point = coordinates[left_index]
        next_point = coordinates[right_index]
        dis = cal_haversine_dis(cur_point, next_point)
        if segment_dis_list[i] >= time_limit * dis and segment_dis_list[i + 1] >= time_limit * dis:
            noise_list.extend(list(range(left_index + 1, right_index)))

    noise_info["noise_num"] = len(noise_list)
    noise_info["noise_points"] = data.iloc[noise_list].to_dict(orient='records')

    return noise_info, noise_list

def get_missing_info(data, missing_segment_lower=10.0, missing_segment_upper=50.0):
    """
    获取缺失段信息
    :param data: 轨迹数据
    :param missing_segment_lower: 缺失段下限
    :param missing_segment_upper: 缺失段上限
    :return: 缺失段信息、缺失段明细
    """
    missing_info = {"missing_num": 0, "missing_points": [],
                    "max_length": 0, "sum_missing_length": 0, "mean_missing_length": 0, "missing_rate": 0}

    # 计算相邻点之间的距离
    distances = cal_haversine_dis_vector(data)

    # 确定两点间的最大距离
    max_missing_length = round(max(distances) / 1000, 3)
    missing_info["max_length"] = max_missing_length

    detected_missing_segments = np.where((distances >= missing_segment_lower * 1000) & (distances <= missing_segment_upper * 1000))[0]
    segment_dis_list = distances[detected_missing_segments]


    if len(detected_missing_segments) == 0:
        print("未识别到缺失段")
        return missing_info, []

    # 调整为轨迹点对：列表表达式；广播机制 + 按列堆叠
    detected_missing_segments = np.column_stack((detected_missing_segments, detected_missing_segments + 1))

    missing_info["missing_num"] = len(detected_missing_segments)
    missing_info["sum_missing_length"] = round(detected_missing_segments.sum() / 1000, 3)
    missing_info["mean_missing_length"] = round(detected_missing_segments.mean() / 1000, 3)
    # 计算轨迹总长度
    total_length = round(distances.sum() / 1000, 3)
    missing_info["missing_rate"] = round(missing_info["sum_missing_length"] / total_length, 3)

    missing_segments = []
    for dis, points in zip(segment_dis_list, detected_missing_segments):
        missing = data.loc[points, ['lng', 'lat', 'timestamp']].to_dict(orient='records')
        delta_t = missing[1]['timestamp'] - missing[0]['timestamp']

        # {'start':{'lng','lat','timestamp'}, 'end':{'lng','lat','timestamp'}, 'length', 'interval'}
        missing_segments.append({'start': missing[0], 'end': missing[1], 'length': dis, 'interval': delta_t})
    missing_info["missing_points"] = missing_segments

    return missing_info, missing_segments

def get_traj_info(data, noise_flag=False, missing_flag=False):
    """
    分析轨迹关键信息：轨迹里程、采样间隔、噪点信息（可选）、缺失段信息（可选）
    :param data: 轨迹数据
    :param noise_flag: 是否记录噪点信息
    :param missing_flag: 是否记录缺失段信息
    :return: 轨迹关键信息
    """

    # 计算相邻点之间的距离
    distances = cal_haversine_dis_vector(data)

    # 计算轨迹总长度
    total_length = round(distances.sum() / 1000, 3)

    # 计算平均采样间隔：相邻点时间间隔的平均值
    timestamps = data["timestamp"].values
    mean_time_interval = round((timestamps[1:] - timestamps[:-1]).mean() / 1000, 3)
    traj_info = {"total_mileage": total_length,
                 "mean_time_interval": mean_time_interval}
    if noise_flag:
        noise_info, noise_list = get_noise_info(data)
        traj_info["noise_info"] = noise_info
        if len(noise_list) == 0:
            print("未识别到噪点")

    if missing_flag:
        missing_info, missing_segments = get_missing_info(data)

        traj_info["missing_info"] = missing_info
        if len(missing_segments) == 0:
            print("未识别到缺失段")

    return traj_info


if __name__ == '__main__':
    # 示例：计算两个点之间的方位角
    lat1, lon1 = 39.9042, 116.4074  # 北京
    # lat2, lon2 = 39.9042, 116.4074  # 北京
    lat2, lon2 = 31.2304, 121.4737  # 上海

    # bearing = cal_bearing(lon1, lat1, lon2, lat2)
    # print(bearing)
    # print(f"两点之间的连线与正北方向的夹角为: {bearing:.2f} 度")

    # d = cal_haversine_dis([lon1, lat1], [lon2, lat2])
    # print(d)

    # segment = split_segment([1, 2, 3, 5, 7, 8, 10])
    # print(segment)

    path = r'../data/raw_data'
    file = '孤立噪点.json'
    with open(os.path.join(path, file), encoding='utf-8') as f:
        data = json.load(f)
    data, _ = geojson_to_pd(data)
    get_traj_info(data, noise_flag=True, missing_flag=True)
