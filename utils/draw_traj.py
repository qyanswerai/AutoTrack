import os
import json
import pandas as pd
import folium
from folium.plugins import MeasureControl


class DrawGPS:
    def __init__(self, path, save_path, file_name, data_type="csv", coord_type="gcj02"):
        self.path = path
        self.save_path = save_path
        self.file_name = file_name
        self.data_type = data_type
        self.coord_type = coord_type

        if not os.path.exists(self.save_path):
            os.makedirs(self.save_path)

        # self.m = folium.Map(location=[30.574948, 104.064593], zoom_start=4)
        if coord_type == "gcj02":
            tiles = 'http://webrd02.is.autonavi.com/appmaptile?lang=zh_cn&size=1&scale=1&style=8&x={x}&y={y}&z={z}'
            attr = '&copy; <a href="http://ditu.amap.com/">高德地图</a>'
        elif coord_type == "bd09ll":
            tiles = 'http://online1.map.bdimg.com/tile/?qt=tile&x={x}&y={y}&z={z}&styles=pl&scaler=1&p=1',
            attr = '&copy; <a href="http://map.baidu.com/">百度地图</a>'
        else:
            tiles = "OpenStreetMap"
            attr = None
        map_params = {"location": [30.574948, 104.064593], "zoom_start": 6, "tiles": tiles, "attr": attr}
        self.m = folium.Map(**map_params)

    def __coord_to_wgs84(self):

        pass

    def draw_track(self):
        file_path = os.path.join(self.path, self.file_name + '.' + self.data_type)
        if self.data_type == 'csv':
            data = pd.read_csv(file_path)
            # 绘制轨迹
            trajectory_layer = folium.FeatureGroup(name="gps").add_to(self.m)
            folium.PolyLine(locations=data[['lat', 'lng']].values, color='blue', weight=2.5,
                            opacity=0.8).add_to(trajectory_layer)

            # 添加起点、终点
            # folium.CircleMarker(location=[point[3], point[2]],
            #                     radius=5,
            #                     color='yellow',
            #                     fill=True,
            #                     fill_color='yellow',
            #                     fill_opacity=0.6,
            #                     popup=text).add_to(missing_segment_layer)
        else:
            with open(file_path, encoding='utf-8') as f:
                geojson_data = json.load(f)
            # json格式的轨迹点坐标系为GCJ02
            folium.GeoJson(geojson_data, name='gps', color='blue', weight=2.5, opacity=0.8).add_to(self.m)

    def process(self):
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
    # file_name = '1743080918402'
    file_name = '1743080892831'

    params = {"path": path, "save_path": save_path, "file_name": file_name, "data_type": "json", "coord_type": "WGS84"}
    # 绘制轨迹
    draw_gps = DrawGPS(**params)
    draw_gps.process()

