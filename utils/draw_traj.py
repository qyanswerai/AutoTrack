import os
import json
import pandas as pd
import folium
from folium.plugins import MeasureControl
from utils.basic_utils import geojson_to_pd


class DrawGPS:
    def __init__(self, path, save_path, file_name, data_type="csv", coord_type="gcj02"):
        self.path = path
        self.save_path = save_path
        self.file_name = file_name
        self.data_type = data_type
        self.coord_type = coord_type

        self.data = None
        self.pd_data = None
        # 可视化地图的初始化视角位置
        self.view_point = None

        if not os.path.exists(self.save_path):
            os.makedirs(self.save_path)

        # 解析文件，并确定coord_type
        file_path = os.path.join(self.path, self.file_name + '.' + self.data_type)
        if "json" == self.data_type:
            with open(file_path, encoding='utf-8') as f:
                self.data = json.load(f)

            if "type" in self.data and self.data["type"] == "FeatureCollection":
                self.geojson_flag = True
                # 以轨迹文件中的coord_type为准
                if "generate_info" in self.data["meta"]:
                    self.coord_type = self.data["meta"]["generate_info"]["result_coord_type"]
                self.view_point = [self.data["meta"]["start_point"]["lat"], self.data["meta"]["start_point"]["lng"]]
                self.pd_data, _ = geojson_to_pd(self.data)
            else:
                print("轨迹数据为json格式，但不符合geojson的字段标准")
                raise Exception('轨迹数据为json格式时，需要符合geojson的字段标准')

        else:
            self.data = pd.read_csv(file_path)
            self.pd_data = self.data.copy(deep=True)
            self.view_point = self.pd_data.iloc[0][['lat', 'lng']].values

        # folium默认使用OpenStreetMap作为底图，为了避免加载不出来，可以替换为高德、百度的瓦片地图（需要与coord_type匹配，不然会偏移）
        if self.coord_type == "gcj02":
            tiles = 'http://webrd02.is.autonavi.com/appmaptile?lang=zh_cn&size=1&scale=1&style=8&x={x}&y={y}&z={z}'
            attr = '&copy; <a href="http://ditu.amap.com/">高德地图</a>'
        elif self.coord_type == "bd09ll":
            tiles = 'http://online1.map.bdimg.com/tile/?qt=tile&x={x}&y={y}&z={z}&styles=pl&scaler=1&p=1',
            attr = '&copy; <a href="http://map.baidu.com/">百度地图</a>'
        else:
            tiles = "OpenStreetMap"
            attr = None

        map_params = {"location": self.view_point, "zoom_start": 9, "tiles": tiles, "attr": attr}
        self.m = folium.Map(**map_params)

    def draw_track(self):
        """
        绘制轨迹、起终点
        :return:
        """
        # 使用GeoJson直接绘图，不能灵活设置图层、样式（不建议使用）
        # if "json" == self.data_type:
        #     folium.GeoJson(self.data, name='gps', color='blue', weight=2.5, opacity=0.8).add_to(self.m)

        # 绘制轨迹
        trajectory_layer = folium.FeatureGroup(name="gps").add_to(self.m)
        folium.PolyLine(locations=self.pd_data[['lat', 'lng']].values, color='blue', weight=2.5,
                        opacity=0.8).add_to(trajectory_layer)

        # 添加起点、终点
        origin_layer = folium.FeatureGroup(name="origin").add_to(self.m)
        folium.CircleMarker(location=self.pd_data.iloc[0][['lat', 'lng']].values,
                            radius=5, color='yellow', fill=True, fill_color='yellow', fill_opacity=0.6,
                            popup="起点").add_to(origin_layer)

        destination_layer = folium.FeatureGroup(name="destination").add_to(self.m)
        folium.CircleMarker(location=self.pd_data.iloc[-1][['lat', 'lng']].values,
                            radius=5, color='yellow', fill=True, fill_color='yellow', fill_opacity=0.6,
                            popup="终点").add_to(destination_layer)

    def process(self):
        """
        绘图主流程：绘制轨迹及起终点、添加测距控件、保存文件
        :return:
        """
        self.draw_track()

        # 添加测距控件
        measure_control = MeasureControl(
            position='bottomleft',  # 控件的位置
            active_color='orange',  # 测量时线条的颜色
            completed_color='red'  # 测量完成后线条的颜色
        )

        self.m.add_child(measure_control)
        folium.LayerControl().add_to(self.m)
        self.m.save(os.path.join(self.save_path, self.file_name + '.html'))


if __name__ == '__main__':
    path = '../data/result_data'
    save_path = '../data/result_data/gps_data'
    file_name = '1765598740674'

    params = {"path": path, "save_path": save_path, "file_name": file_name, "data_type": "json", "coord_type": "wgs84"}
    # 绘制轨迹
    draw_gps = DrawGPS(**params)
    draw_gps.process()

