**轨迹数据**对于分析车辆历史或实时的行驶状况至关重要，其核心字段包括**经纬度坐标、时间戳、速度、航向角**等

[AutoTraj库的【轨迹获取模块】](https://github.com/qyanswerai/AutoTraj)能够生成字段齐全的轨迹数据
**项目地址：[https://github.com/qyanswerai/AutoTraj](https://github.com/qyanswerai/AutoTraj)**

![在这里插入图片描述](https://i-blog.csdnimg.cn/direct/725320cf16294652a3eddd48d8a8ce29.png)

**【核心功能说明】**
- **【获取经纬度】**：给定起点、终点坐标，调用高德、百度、`OpenRouteService`（简称`amap`、`baidu`、`ors`）的相关接口或方法获取起终点之间的路线（路线上各个点的经纬度坐标）
- **【计算航向角】**：根据相邻点的坐标采用公式计算`direction`，正北为0，顺时针递增（0~360.0）
- **【生成速度及时间戳】**：进一步通过行驶状态模拟生成速度、时间戳字段，得到字段齐全的轨迹点，可用于轨迹分析（例如识别停留、低速段），轨迹重合率计算等
# 一、输入及输出
## 1.1、输入及示例
| 参数名           | 类型 | 是否必填 | 含义       | 说明                                                         | 默认值 |
| ---------------- | ---- | -------- | ---------- | ------------------------------------------------------------ | ------ |
| origin           | str  | 是       | 起点坐标   | 经度在前，纬度在后，经度和纬度以","分隔<br />坐标精确到小数点后6位即可 | 无     |
| destination      | str  | 是       | 终点坐标   | 经度在前，纬度在后，经度和纬度用","分割                      | 无     |
| way_points       | str  | 否       | 途径点坐标 | 每个途径点经纬度以","分割，多个途径点坐标按顺序以";"分隔<br />最多支持16个途经点（method_type为baidu时，最多18个途径点；method_type为ors时，无明确限制） | ""     |
| method_type      | str  | 否       | 方法   | 获取轨迹的方式：高德amap、百度baidu、开源库ors               | amap   |
| coord_type       | str  | 否       | 坐标系 | 起点、终点、途径点坐标系：国际坐标wgs84、高德gcj02、百度bd09ll<br />-_- 说明：bd09ll后面两个是小写L | gcj02  |
| other_params     | dict | 否       | 其他参数   | 其他参数：高德API、百度API、ors库所支持的其他参数，详见链接<br />高德：https://lbs.amap.com/api/webservice/guide/api/newroute#t4<br />百度：https://lbsyun.baidu.com/faq/api?title=webapi/webservice-direction/dirve<br/>ors库：https://openrouteservice.org/dev/#/api-docs/v2/directions | None   |
| interpolate_flag | bool | 否       | 是否插点   | 获取路线规划的结果后，可以在线上等距插点（增加点的密度）     | False  |
| simulate_flag        | bool  | 否       | 是否新增字段   | 默认通过驾驶状态模拟确定时间戳、速度、航向角字段                           | True     |
| result_coord_type        | str  | 否       | 结果坐标系   | 指定所获取的轨迹点的坐标系                          | wgs84     |
| save_path        | str  | 否       | 保存路径   | 默认保存在data/result_data文件夹下                           | ""     |
| save_name        | str  | 否       | 保存名称   | 可以指定文件名，需要符合命名规范，若不指定则以文件保存时刻的Unix时间戳作为文件名 | ""     |
| result_type      | str  | 否       | 保存类型   | 文件类型：表格型csv、字典型json                              | csv    |

```json
{
    "origin": "116.481028,39.989643",
    "destination": "116.434446,39.90816",
    "way_points": "116.461028,39.959643;116.441028,39.929643",
    "method_type": "amap",
    "coord_type": "gcj02",
    "other_params": {
        "show_fields": "polyline",    // 高德API参数：不设置时只返回基础信息，若需返回多个字段则以“,”分隔
        "cartype": 0,    // 百度API参数：0表示普通汽车，1表示纯电动汽车
        "profile": "driving-car",    // ors库参数：driving-car表示汽车，driving-car表示货车
        "format": "geojson"    // ors库参数：不设置时需解码才能提取坐标，设置为geojson则返回geojson格式的结果（方便提取坐标）
    },
    "interpolate_flag": false,
    "simulate_flag": false,
    "result_coord_type": "wgs84",
    "save_path": "data/result_data",
    "save_name": "test_01",
    "result_type": "csv"
}
```

【入参说明】
- 若未给定`save_path`，则不保存轨迹文件
- 建议`method_type`与`coord_type`相互匹配：`amap`与`gcj02`、`baidu`与`bd09ll`、`ors`与`wgs84`
- 若不匹配则需转换坐标系（自动完成）：例如`method_type`为`amap`，`coord_type`为`wgs84`，则坐标系先转换为`gcj02`再调用`API`获取轨迹
- 若起点`origin`或终点`destination`不在国内，则`method_type`只能为`ors`（入参检查时会自动转换）
## 1.2、输出及示例
| 参数名            | 类型  | 是否必填 | 含义       | 说明                                                         | 默认值            |
| ----------------- | ----- | -------- | ---------- | ------------------------------------------------------------ | ----------------- |
| origin            | str   | 是       | 起点坐标   |                                                              | 与输入相同        |
| destination       | str   | 是       | 终点坐标   |                                                              | 与输入相同        |
| way_points        | str   | 是       | 途径点坐标 |                                                              | 与输入相同        |
| final_method_type | str   | 是       | 方法类型   |                                                              | 与method_type相同 |
| result_coord_type | str   | 是       | 坐标系类型 |                                                              | wgs84             |
| traj_points       | list  | 是       | 轨迹数据   | 获取的轨迹点，字段齐全                                       | []                |
| lng               | float | 否       | 经度       | 坐标系为final_method_type                                    |                   |
| lat               | float | 否       | 纬度       | 坐标系为final_method_type                                    |                   |
| timestamp         | int64 | 否       | 时间戳     | Unix格式时间戳，精确到毫秒（以整数形式存储时需注意大小，13位） |                   |
| direction         | float | 否       | 航向角     | 范围0.0~360.0，正北为0，顺时针递增                           |                   |
| speed             | float | 否       | 速度       | 轨迹点瞬时速度，单位为km/h                                   |                   |

```json
{
    "origin": "116.481028,39.989643",
    "destination": "116.434446,39.90816",
    "way_points": "116.461028,39.959643;116.441028,39.929643",
    "final_method_type": "amap",
    "result_coord_type": "wgs84",
    "traj_points": [
        {"lng": 104.21018, "lat":30.525391, "timestamp": 1728762988000, "speed": 15.3, "direction": 135},
        {"lng": 104.210473, "lat":30.525124, "timestamp": 1728763000000, "speed": 2.0, "direction": 141},
        {"lng": 104.210488, "lat":30.525114, "timestamp": 1728763012000, "speed":0.0, "direction": 120},
        ...
        ]
}
```
# 二、流程详解
## 2.1、轨迹获取
**【准备工作】**：获取密钥，修改`config.ini`
- 设置合适的`API Key`名称，可以便于识别该密钥的用途
- 选择合适的权限范围，根据实际需求进行选择
- 高德`key`申请：[https://lbs.amap.com/api/webservice/create-project-and-key](https://lbs.amap.com/api/webservice/create-project-and-key)
- 百度`ak`申请：[https://lbsyun.baidu.com/faq/search?id=299](https://lbsyun.baidu.com/faq/search?id=299)
- `ors key`申请：[https://openrouteservice.org/](https://openrouteservice.org/)
	- 注册账号并登录，进入个人中心（点击右上角的用户名）
	- 可以看到`API keys`，点击`Generate API key`

**【给定输入】**：参照输入字段说明及示例

【轨迹获取主流程】：`main.py`接收输入，调用`traj_acquisition`模块的`traj_acquisition.py`
- 根据指定的`method_type`调用`API`获取轨迹，若失败则尝试其他备选方法
- 若`interpolate_flag == True`，则通过等距插值补充轨迹点
- 若`simulate_flag == True`，则调用`traj_acquisition`模块的`traj_info_perfection.py`
	- 通过车辆行驶状态模拟获取速度、时间戳、航向角字段（`speed`、`timestamp`）
- 否则，轨迹点只包含经纬度坐标字段（`lng`、`lat`），可以根据坐标计算航向角（`direction`）

**【获取输出】**：参照输出字段说明及示例
## 2.2、字段补全
### 2.2.1、字段补全思路
通过调用路径规划接口能获取轨迹点的坐标（`lng`、`lat`），根据坐标字段可以计算航向角（`direction`），但是还缺少时间戳、速度字段（`timestamp`、`speed`），本算法通过**车辆行驶状态模拟**得到
- **计算`direction`**：根据相邻点的坐标采用公式计算`direction`，正北为0，顺时针递增（0~360.0）
- **生成`speed`**：根据车辆行驶状态模拟得到每个轨迹点的速度（详见下文说明）
	- 给定初始速度、初始加速度状态
	- 计算下一时刻的速度，根据对应的状态转移概率得到下一时刻的加速度状态
	- 重复执行，确定所有轨迹点的速度
- **生成`timestamp`**：根据轨迹点的坐标、速度计算
	- 给定初始时间戳
	- 根据相邻点坐标采用公式计算距离，以两个点的速度均值作为路段的速度（若速度为0，则时间戳直接增加10秒），根据距离、速度计算路段的行程时间，进而得到时间戳
	- 重复执行，确定所有轨迹点的时间戳
### 2.2.2、速度生成
为了**精细化模拟车辆行驶状态**，**将车辆状态细分为速度状态、加速度状态**
- **速度状态**：低速（0-50）、中速（50-70）、高速（70-90）、超高速（90-100）
- **加速度状态**：加速（速度增大）、减速（速度减小）、巡航（速度上下波动）
- 最大速度默认为100km/h（以上数值适用于货车，可根据需要修改，例如小汽车最大速度可设置为120）
- 速度调整：生成给定区间内的随机值（与速度状态有关），与当前速度做差或求和

**状态转移说明（可结合代码辅助理解）：已知`t`时刻的车辆状态（例如【低速 + 加速】）**
- 则可以根据【低速 + 加速】确定`t+1`时刻的速度（当前速度加上一个给定区间内的随机值）
- 同样根据【低速 + 加速】对应的状态转移概率确定`t+1`时刻的状态
```json
{
    "low_speed": {
                     "accelerate": [0.8, 0.1, 0.1], 
                     "decelerate": [0.1, 0.8, 0.1],  
                     "cruise": [0.3, 0.3, 0.4]
                 },
    "mid_speed": {
                     "accelerate": [0.6, 0.1, 0.3],
                     "decelerate": [0.2, 0.5, 0.3],
                     "cruise": [0.3, 0.2, 0.5]
                 },
    "high_speed": {
                      "accelerate": [0.4, 0.2, 0.4],
                      "decelerate": [0.1, 0.5, 0.4],
                      "cruise": [0.1, 0.1, 0.8]
                  },
    "super_high_speed": {
                            "accelerate": [0.3, 0.4, 0.3],
                            "decelerate": [0.1, 0.6, 0.3],
                            "cruise": [0.2, 0.4, 0.4]
                        }
}
```
![在这里插入图片描述](https://i-blog.csdnimg.cn/direct/0ad06031a70e4ef5b82aded5b34f2794.png)

以300个轨迹点为例，生成的速度值如下图所示：
![在这里插入图片描述](https://i-blog.csdnimg.cn/direct/bdc332facc7f494bacc076c806d87d7b.png)

## 2.3、轨迹可视化
读取轨迹文件，使用`folium`库绘制轨迹

| 参数名     | 类型 | 是否必填 | 含义       | 说明                                     | 默认值 |
| ---------- | ---- | -------- | ---------- | ---------------------------------------- | ------ |
| path       | str  | 是       | 轨迹路径   | 需进行可视化的轨迹数据路径               |        |
| save_path  | str  | 是       | 保存路径   | 轨迹可视化结果保存路径                   |        |
| file_name  | str  | 是       | 文件名称   | 需进行可视化的轨迹数据文件名             |        |
| data_type  | str  | 否       | 文件类型   | 文件类型：表格型csv、字典型json          | csv    |
| coord_type | str  | 否       | 坐标系类型 | 轨迹数据坐标系类型：wgs84、gcj02、bd09ll | gcj02  |
- 注意事项
	- 轨迹数据的坐标系为`wgs84`时（使用`OpenStreetMap`作为底图），可能加载失败，建议转换为其他坐标系再尝试绘图
	- 可视化结果为与`file_name`相同的`html`文件，可使用浏览器打开
# 三、补充说明
## 3.1、时间戳

> **！！！重要！！！**
>- 对于轨迹数据，时间戳是非常重要的字段，仅次于坐标字段
>- 为了避免时间戳转换的风险（需考虑时区），建议处理及存储时始终使用`Unix`格式（13位，精确到毫秒），而不是转换为`'%Y-%m%-d %H:%M:%S'`等形式

## 3.2、Geojson
相关链接：[https://leafletjs.com/examples/geojson/](https://leafletjs.com/examples/geojson/)

一个典型的`Geojson`文件包含一个要素集合对象，用于表示一组相关的地理要素
- 可以在`meta`（非必要）中设置要素集合对象的相关属性
- 要素集合对象必须包含`type`（值为 `FeatureCollection`）和`features`（要素对象数组）
	- `features`中可以记录点`Point`、线`LineString`等信息
	- `type`（值为`Feature`）和`geometry`（地理属性）是必要的，其他信息可以放在`properties`中

一个可用于轨迹可视化的`Geojson`文件如下所示（包含起点、终点、轨迹线）：
[https://github.com/qyanswerai/AutoTraj/blob/master/data/result_data/gps_data/1745330067766.html](https://github.com/qyanswerai/AutoTraj/blob/master/data/result_data/gps_data/1745330067766.html)
## 3.3、Folium

> **使用`Folium`进行轨迹的可视化：绘制轨迹、起终点、增加测距功能等（简单的交互）**
> - **要求坐标系为`WGS84`**
> - **纬度在前，经度在后**

相关教程：[【python交互式地图数据可视化神器folium】](https://www.bilibili.com/video/BV1t3411A7Z8/?share_source=copy_web&vd_source=c71860a35ae6f457f141a44ee4b38133) 

示例代码：[https://github.com/qyanswerai/AutoTraj/blob/master/utils/draw_traj.py](https://github.com/qyanswerai/AutoTraj/blob/master/utils/draw_traj.py)

