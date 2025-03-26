import math


class CoordinatesTransform:
    def __init__(self):
        self.x_pi = math.pi * 3000.0 / 180.0
        self.pi = math.pi
        self.a = 6378245.0  # 长半轴
        self.es = 0.00669342162296594323  # 偏心率平方

    def is_in_china(self, lng, lat):
        """粗略判断坐标是否在中国范围内（适用于大部分场景）"""
        return 73.66 <= lng <= 135.05 and 3.86 <= lat <= 53.55

    def wgs84_to_gcj02(self, lng, lat):
        # 若不在中国国内，直接返回wgs84坐标系下的坐标
        if not self.is_in_china(lng, lat):
            return lng, lat

        d_lat = self.transform_lat(lng - 105.0, lat - 35.0)
        d_lng = self.transform_lng(lng - 105.0, lat - 35.0)
        rad_lat = lat / 180.0 * self.pi
        magic = math.sin(rad_lat)
        magic = 1 - self.es * magic * magic
        magic_sqrt = math.sqrt(magic)
        d_lat = (d_lat * 180.0) / ((self.a * (1 - self.es)) / (magic * magic_sqrt) * self.pi)
        d_lng = (d_lng * 180.0) / (self.a / magic_sqrt * math.cos(rad_lat) * self.pi)
        gcj_lat = lat + d_lat
        gcj_lng = lng + d_lng
        return gcj_lng, gcj_lat

    def gcj02_to_wgs84(self, lng, lat):
        d_lat = self.transform_lat(lng - 105.0, lat - 35.0)
        d_lng = self.transform_lng(lng - 105.0, lat - 35.0)
        rad_lat = lat / 180.0 * self.pi
        magic = math.sin(rad_lat)
        magic = 1 - self.es * magic * magic
        magic_sqrt = math.sqrt(magic)
        d_lat = (d_lat * 180.0) / ((self.a * (1 - self.es)) / (magic * magic_sqrt) * self.pi)
        d_lng = (d_lng * 180.0) / (self.a / magic_sqrt * math.cos(rad_lat) * self.pi)
        wgs_lng = lng * 2 - lng - d_lng
        wgs_lat = lat * 2 - lat - d_lat
        return wgs_lng, wgs_lat

    def transform_lat(self, lng, lat):
        ret = -100.0 + 2.0 * lng + 3.0 * lat + 0.2 * lat * lat + \
              0.1 * lng * lat + 0.2 * math.sqrt(math.fabs(lng))
        ret += (20.0 * math.sin(6.0 * lng * self.pi) + 20.0 *
                math.sin(2.0 * lng * self.pi)) * 2.0 / 3.0
        ret += (20.0 * math.sin(lat * self.pi) + 40.0 *
                math.sin(lat / 3.0 * self.pi)) * 2.0 / 3.0
        ret += (160.0 * math.sin(lat / 12.0 * self.pi) + 320 *
                math.sin(lat * self.pi / 30.0)) * 2.0 / 3.0
        return ret

    def transform_lng(self, lng, lat):
        ret = 300.0 + lng + 2.0 * lat + 0.1 * lng * lng + \
              0.1 * lng * lat + 0.1 * math.sqrt(math.fabs(lng))
        ret += (20.0 * math.sin(6.0 * lng * self.pi) + 20.0 *
                math.sin(2.0 * lng * self.pi)) * 2.0 / 3.0
        ret += (20.0 * math.sin(lng * self.pi) + 40.0 *
                math.sin(lng / 3.0 * self.pi)) * 2.0 / 3.0
        ret += (150.0 * math.sin(lng / 12.0 * self.pi) + 300.0 *
                math.sin(lng / 30.0 * self.pi)) * 2.0 / 3.0
        return ret

    # GCJ02转BD09（火星坐标系转百度坐标系）
    def gcj02_to_bd09(self, lng, lat):
        z = math.sqrt(lng * lng + lat * lat) + 0.00002 * math.sin(lat * self.x_pi)
        theta = math.atan2(lat, lng) + 0.000003 * math.cos(lng * self.x_pi)
        bd_lng = z * math.cos(theta) + 0.0065
        bd_lat = z * math.sin(theta) + 0.006
        return bd_lng, bd_lat

    # BD09转GCJ02（百度坐标系转火星坐标系）
    def bd09_to_gcj02(self, lng, lat):
        x = lng - 0.0065
        y = lat - 0.006
        z = math.sqrt(x * x + y * y) - 0.00002 * math.sin(y * self.x_pi)
        theta = math.atan2(y, x) - 0.000003 * math.cos(x * self.x_pi)
        gcj_lng = z * math.cos(theta)
        gcj_lat = z * math.sin(theta)
        return gcj_lng, gcj_lat

    # WGS84转BD09（GPS转百度坐标系）
    def wgs84_to_bd09(self, lng, lat):
        gcj02 = self.wgs84_to_gcj02(lng, lat)
        return self.gcj02_to_bd09(gcj02[0], gcj02[1])

    # BD09转WGS84（百度坐标系转GPS）
    def bd09_to_wgs84(self, lng, lat):
        gcj02 = self.bd09_to_gcj02(lng, lat)
        return self.gcj02_to_wgs84(gcj02[0], gcj02[1])

    def coord_transform(self, coord, from_coord_type, to_coord_type, coord_type='str'):
        if coord_type == 'str':
            coord_list = [list(map(float, coord.split(','))) for coord in coord.split(';')]
        else:
            coord_list = coord
        result_list = coord_list
        if 'gcj02' == from_coord_type:
            if 'wgs84' == to_coord_type:
                result_list = [list(self.gcj02_to_wgs84(*coord)) for coord in coord_list]
            if 'bd09ll' == to_coord_type:
                result_list = [list(self.gcj02_to_bd09(*coord)) for coord in coord_list]
        elif 'wgs84' == from_coord_type:
            if 'gcj02' == to_coord_type:
                result_list = [list(self.wgs84_to_gcj02(*coord)) for coord in coord_list]
            if 'bd09ll' == to_coord_type:
                result_list = [list(self.wgs84_to_bd09(*coord)) for coord in coord_list]
        else:
            if 'wgs84' == to_coord_type:
                result_list = [list(self.bd09_to_wgs84(*coord)) for coord in coord_list]
            if 'gcj02' == to_coord_type:
                result_list = [list(self.bd09_to_gcj02(*coord)) for coord in coord_list]

        return result_list


if __name__ == '__main__':
    ct = CoordinatesTransform()
    lng = 118.994396
    lat = 36.718905
    print('lng:', lng, 'lat:',lat)

    # gcj02转换为wgs84
    lng_wgs84, lat_wgs84 = ct.gcj02_to_wgs84(lng, lat)
    print('gcj02转换为wgs84')
    print('lng_wgs84:', lng_wgs84, 'lat_wgs84:',lat_wgs84)

    # wgs84转换为gcj02
    lng_gcj02, lat_gcj02 = ct.wgs84_to_gcj02(lng, lat)
    print('wgs84转换为gcj02')
    print('lng_gcj02:', lng_gcj02, 'lat_gcj02:',lat_gcj02)

    # gcj02转换为bd09
    lng_bd09, lat_bd09 = ct.gcj02_to_bd09(lng, lat)
    print('gcj02转换为bd09')
    print('lng_bd09:', lng_bd09, 'lat_bd09:', lat_bd09)

    # bd09转换为gcj02
    lng_gcj02, lat_gcj02 = ct.bd09_to_gcj02(lng, lat)
    print('bd09转换为gcj02')
    print('lng_gcj02:', lng_gcj02, 'lat_gcj02:', lat_gcj02)

    print('finished')
