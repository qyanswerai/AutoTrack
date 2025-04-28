import math
import datetime
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

from utils.basic_utils import cal_bearing, cal_haversine_dis, split_segment


class DrivingStateSimulate:
    def __init__(self, raw_data, start_time="2014-06-07 08:00:00", max_speed=100,
                 lower_time_interval=5, upper_time_interval=30, stop_flag=False, stop_num=5):
        self.traj_data = raw_data.copy()
        self.start_time = start_time
        self.max_speed = max_speed
        self.lower_time_interval = lower_time_interval
        self.upper_time_interval = upper_time_interval
        self.stop_flag = stop_flag
        self.stop_num = stop_num

        self.start_time = datetime.datetime.strptime(self.start_time, "%Y-%m-%d %H:%M:%S")

        # 通过调整状态转移概率，使稳定行驶的速度维持在70~80km/h之间
        self.state_transform_info = {"low_speed": {"accelerate": [0.8, 0.1, 0.1],
                                                   "decelerate": [0.1, 0.8, 0.1],
                                                   "cruise": [0.3, 0.3, 0.4]},
                                     "mid_speed": {"accelerate": [0.6, 0.1, 0.3],
                                                   "decelerate": [0.2, 0.5, 0.3],
                                                   "cruise": [0.3, 0.2, 0.5]},
                                     "high_speed": {"accelerate": [0.4, 0.2, 0.4],
                                                    "decelerate": [0.1, 0.5, 0.4],
                                                    "cruise": [0.1, 0.1, 0.8]},
                                     "super_high_speed": {"accelerate": [0.3, 0.4, 0.3],
                                                          "decelerate": [0.1, 0.6, 0.3],
                                                          "cruise": [0.2, 0.4, 0.4]}
                                     }

    def __generate_speed(self):
        """
        生成速度
        :return:
        """
        def get_speed_state(speed):
            """
            确定速度状态：低速、中速、高速、超高速
            :param speed: 速度（单位：km/h）
            :return: 速度状态
            """
            if speed < 50:
                ss = "low_speed"
            elif speed < 70:
                ss = "mid_speed"
            elif speed < 90:
                ss = "high_speed"
            else:
                ss = "super_high_speed"
            return ss

        def get_next_state(speed_state, state):
            """
            根据速度状态、加速度状态确定下一时刻的加速度状态
            :param speed_state: 速度状态
            :param state: 加速度状态
            :return: 下一时刻的加速度状态
            """
            state_probability = self.state_transform_info[speed_state][state]
            value = np.random.uniform(0, 1)
            if value < state_probability[0]:
                return "accelerate"
            elif value < state_probability[0] + state_probability[1]:
                return "decelerate"
            else:
                return "cruise"

        speed_list = []
        speed = 10
        state = "accelerate"
        for i in range(len(self.traj_data)):
            speed_list.append(speed)

            ss = get_speed_state(speed)

            # update speed
            if state == 'accelerate':
                if ss == 'high_speed' or ss == 'super_high_speed':
                    low, high = 2, 6
                else:
                    low, high = 4, 8
                speed += np.random.uniform(low, high)
            elif state == 'decelerate':
                if ss == 'high_speed' or ss == 'super_high_speed':
                    low, high = 4, 8
                else:
                    low, high = 2, 6
                speed -= np.random.uniform(low, high)
            else:
                speed += np.random.uniform(-2, 2)

            speed = min(max(0.0, round(speed, 2)), self.max_speed)

            # update state
            state = get_next_state(ss, state)

        # plt.plot(speed_list)
        # plt.show()
        self.traj_data["speed"] = speed_list

    def __generate_timestamp(self):
        """
        生成时间戳
        :return:
        """
        self.traj_data['lng_up'] = self.traj_data['lng'].shift(1)
        self.traj_data['lat_up'] = self.traj_data['lat'].shift(1)
        self.traj_data[['lng_up', 'lat_up']] = self.traj_data[['lng_up', 'lat_up']].bfill()

        self.traj_data['distance'] = self.traj_data.apply(
            lambda row: cal_haversine_dis([row['lng_up'], row['lat_up']], [row['lng'], row['lat']]), axis=1)
        speed_list = self.traj_data['speed'].tolist()
        distance_list = self.traj_data['distance'].tolist()
        timestamp_list = [self.start_time.timestamp() * 1000] * len(self.traj_data)
        for i in range(1, len(distance_list)):
            avg_speed = (speed_list[i] + speed_list[i - 1]) / 2
            # 若速度为0，则固定增加10s
            if avg_speed > 0:
                delta_time = min(max(distance_list[i] / (avg_speed / 3.6), self.lower_time_interval),
                                 self.upper_time_interval)
            else:
                delta_time = 10

            # 单位ms
            timestamp_list[i] = timestamp_list[i - 1] + delta_time * 1000

        self.traj_data['timestamp'] = timestamp_list
        # 指定为int64而不是int，避免超出范围
        self.traj_data['timestamp'] = self.traj_data['timestamp'].astype('int64')
        self.traj_data.drop(columns=['lng_up', 'lat_up', 'distance'], inplace=True)

    def __generate_direction(self):
        """
        计算航向角（已弃用）
        :return:
        """
        self.traj_data['direction'] = self.traj_data.apply(
            lambda row: cal_bearing(row['lng_up'], row['lat_up'], row['lng'], row['lat']), axis=1)

        # 用第2个点的方向角作为第1个点的方向角
        self.traj_data.loc[0, 'direction'] = self.traj_data.loc[1, 'direction']
        self.traj_data.drop(columns=['lng_up', 'lat_up'], inplace=True)

        raw_coordinates = self.traj_data[['lng', 'lat']].values.tolist()
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
            self.traj_data.loc[stay_segment, 'direction'] = direction

    def __generate_stop_segment(self):
        """
        生成“停留段”（轨迹点瞬时速度设为0）
        :return:
        """
        # 直接修改速度
        for i in range(self.stop_num):
            stop_point = np.random.uniform(0, len(self.traj_data) - 1)
            stop_left = max(0, int(stop_point) - 5)
            stop_right = min(len(self.traj_data) - 1, int(stop_point) + 5)
            speeds = [0] * (stop_right - stop_left + 1)
            # 控制停留前后的速度值
            speeds[0] = 30
            speeds[-1] = 30
            self.traj_data.loc[range(stop_left, stop_right + 1), 'speed'] = speeds

    def process(self):
        """
        轨迹字段生成：速度、时间戳
        :return:
        """
        # 生成速度
        self.__generate_speed()
        # 生成时间戳
        self.__generate_timestamp()
        # 生成航向角
        # self.__generate_direction()
        if self.stop_flag:
            self.__generate_stop_segment()
        return self.traj_data


if __name__ == '__main__':
    simulate = DrivingStateSimulate(np.ones(300), stop_flag=True)
    simulate.process()
