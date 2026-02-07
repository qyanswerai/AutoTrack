import os
import folium
from folium.plugins import MeasureControl
from utils.basic_utils import geojson_to_pd, read_track_data


class DrawGPS:
    def __init__(self, path, save_path="", data=None, coord_type="gcj02"):
        # 要求path必须包含文件名，可以包含文件路径
        # 要求save_path可以包含文件名，可以包含文件路径
        # 支持直接传入轨迹数据，要求data为geojson格式
        self.path = path
        self.save_path = save_path
        self.coord_type = coord_type
        self.data = data
        self.pd_data = None
        # 可视化地图的初始化视角位置
        self.view_point = None

        base_name = os.path.basename(self.path)
        save_dir_name = os.path.dirname(self.save_path)
        save_base_name = os.path.basename(self.save_path)
        if self.save_path.endswith(".html"):
            # 例如111.html
            if save_dir_name != "" and not os.path.exists(save_dir_name):
                os.makedirs(self.save_path)

            self.save_path = os.path.join(save_dir_name, save_base_name)
        else:
            # 例如''或者data/result_data
            if save_dir_name != "":
                if not os.path.exists(self.save_path):
                    os.makedirs(self.save_path)
                save_base_name = base_name.split(".")[0] + ".html"
                self.save_path = os.path.join(self.save_path, save_base_name)

    def __prepare_data(self):
        # 支持直接传入轨迹数据，要求data为geojson格式
        if self.data is None:
            self.data = read_track_data(self.path)
        else:
            if "type" not in self.data and self.data["type"] != "FeatureCollection":
                raise Exception('轨迹数据为json格式时，需要符合geojson的字段标准')

        # 以轨迹文件中的coord_type为准
        if "generate_info" in self.data["meta"] and "result_coord_type" in self.data["meta"]["generate_info"]:
            self.coord_type = self.data["meta"]["generate_info"]["result_coord_type"]
        self.view_point = [self.data["meta"]["start_point"]["lat"], self.data["meta"]["start_point"]["lng"]]
        self.pd_data, _ = geojson_to_pd(self.data)

    def __draw_track(self):
        """
        绘制轨迹、起终点
        :return:
        """
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

        # 使用GeoJson直接绘图，不能灵活设置图层、样式（不建议使用）
        # if self.path.endswith("json"):
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

        # 添加测距控件
        measure_control = MeasureControl(
            position='bottomleft',  # 控件的位置
            active_color='orange',  # 测量时线条的颜色
            completed_color='red'  # 测量完成后线条的颜色
        )

        self.m.add_child(measure_control)
        folium.LayerControl().add_to(self.m)

    def process(self):
        """
        绘图主流程：绘制轨迹及起终点、添加测距控件、保存文件
        :return:
        """
        # 读取轨迹数据
        self.__prepare_data()
        # 绘制轨迹
        self.__draw_track()

        # 是否保存文件
        if self.save_path != "":
            self.m.save(self.save_path)


if __name__ == '__main__':
    path = '../data/result_data/1765724700568.json'
    save_path = '../data/result_data/gps_data/'
    params = {"path": path, "save_path": save_path, "coord_type": "wgs84"}

    # 直接传入轨迹数据并绘制
    # import json
    # with open(path, encoding='utf-8') as f:
    #     data = json.load(f)
    # params = {"path": path, "save_path": save_path, "data": data, "coord_type": "wgs84"}

    # 绘制轨迹
    draw_gps = DrawGPS(**params)
    draw_gps.process()

