from itertools import permutations
from math import floor
def get_min_len_path(spList, startPoint):
    def get_pathLen(spList, path):
        pathLen = 0
        for i in range(1, len(path)):
            p1 = spList[path[i-1]]
            p2 = spList[path[i]]
            dir1_len = abs(p1-p2)
            dir2_len = abs(360 - abs(p1-p2))
            if dir1_len < dir2_len:
                pathLen += dir1_len
            else:
                pathLen += dir2_len
        return pathLen
    
    L = len(spList)

    other_points = list(range(L))
    other_points.remove(startPoint)

    all_choices = [x for x in permutations(other_points)]

    min_path_len = float('inf')
    min_path = None

    for i, choice in enumerate(all_choices):
        path = (startPoint,) + choice
        
        pathLen = get_pathLen(spList, path)
        
        if pathLen < min_path_len:
            min_path_len = pathLen
            min_path = path
            
    
    return min_path, min_path_len



import numpy as np
from itertools import combinations


class DualMotorPathOptimizer:
    def __init__(self, motor1_home=30, motor2_home=330, 
                 move_speed=0.0125, photo_time=3, min_distance=20):
        """
        初始化雙馬達路徑優化器
        
        Parameters:
        - motor1_home: 馬達1的初始位置（度）
        - motor2_home: 馬達2的初始位置（度）
        - move_speed: 移動速度（秒/度）
        - photo_time: 拍照時間（秒）
        - min_distance: 最小安全距離（度）
        """
        self.motor1_home = motor1_home
        self.motor2_home = motor2_home
        self.move_speed = move_speed
        self.photo_time = photo_time
        self.min_distance = min_distance
        self.home_position = 0  # 假設home點在0度
        
    def calculate_distance(self, pos1, pos2):
        """計算兩個角度位置之間的最短距離"""
        diff = abs(pos1 - pos2)
        return min(diff, 360 - diff)
    
    def calculate_move_time(self, from_pos, to_pos):
        """計算從一個位置移動到另一個位置的時間"""
        distance = self.calculate_distance(from_pos, to_pos)
        return distance * self.move_speed
    
    def check_collision(self, motor1_pos, motor2_pos):
        """檢查兩個馬達是否會發生碰撞"""
        distance = self.calculate_distance(motor1_pos, motor2_pos)
        return distance < self.min_distance
    
    def calculate_path_time(self, path, start_pos):
        """計算單個馬達完成路徑的總時間"""
        if not path:
            return self.calculate_move_time(start_pos, self.home_position)
        
        total_time = 0
        current_pos = start_pos
        
        # 移動到每個點並拍照
        for target in path:
            total_time += self.calculate_move_time(current_pos, target)
            total_time += self.photo_time
            current_pos = target
        
        # 返回home
        total_time += self.calculate_move_time(current_pos, self.home_position)
        
        return total_time
    
    def simulate_parallel_execution(self, path1, path2):
        """
        模擬兩個馬達並行執行，檢查是否會發生碰撞
        返回：(是否安全, 總時間, 碰撞時刻)
        """
        motor1_pos = self.motor1_home
        motor2_pos = self.motor2_home
        
        # 建立時間軸事件
        events1 = []
        events2 = []
        
        # 馬達1的事件
        time1 = 0
        for target in path1:
            move_time = self.calculate_move_time(motor1_pos, target)
            events1.append(('move', time1, time1 + move_time, motor1_pos, target))
            time1 += move_time
            events1.append(('photo', time1, time1 + self.photo_time, target, target))
            time1 += self.photo_time
            motor1_pos = target
        
        # 馬達1返回home
        move_time = self.calculate_move_time(motor1_pos, self.home_position)
        events1.append(('move', time1, time1 + move_time, motor1_pos, self.home_position))
        
        # 馬達2的事件
        time2 = 0
        motor2_pos = self.motor2_home
        for target in path2:
            move_time = self.calculate_move_time(motor2_pos, target)
            events2.append(('move', time2, time2 + move_time, motor2_pos, target))
            time2 += move_time
            events2.append(('photo', time2, time2 + self.photo_time, target, target))
            time2 += self.photo_time
            motor2_pos = target
        
        # 馬達2返回home
        move_time = self.calculate_move_time(motor2_pos, self.home_position)
        events2.append(('move', time2, time2 + move_time, motor2_pos, self.home_position))
        
        # 檢查碰撞
        max_time = max(time1 + move_time, time2 + move_time)
        check_interval = 0.1  # 每0.1秒檢查一次
        
        for t in np.arange(0, max_time, check_interval):
            # 找出當前時刻兩個馬達的位置
            pos1 = self.get_position_at_time(events1, t)
            pos2 = self.get_position_at_time(events2, t)
            
            if self.check_collision(pos1, pos2):
                return False, max_time, t
        print(max_time)
        return True, max_time, None
    
    def get_position_at_time(self, events, time):
        """獲取某個時刻馬達的位置"""
        for event in events:
            event_type, start_time, end_time, start_pos, end_pos = event
            if start_time <= time <= end_time:
                if event_type == 'photo':
                    return start_pos
                else:  # move
                    # 線性插值
                    progress = (time - start_time) / (end_time - start_time)
                    # 處理角度的線性插值
                    diff = end_pos - start_pos
                    if abs(diff) > 180:
                        if diff > 0:
                            diff -= 360
                        else:
                            diff += 360
                    current_pos = start_pos + progress * diff
                    if current_pos < 0:
                        current_pos += 360
                    elif current_pos >= 360:
                        current_pos -= 360
                    return current_pos
        
        # 如果超過所有事件，返回home位置
        return self.home_position
    
    def plan_1(self, targets):
        n = len(targets)
        best_time = float('inf')
        best_allocation = None
        
        # 嘗試所有可能的分配方式
        for r in range(n + 1):
            for motor1_indices in combinations(range(n), r):
                motor2_indices = [i for i in range(n) if i not in motor1_indices]
                
                path1 = [targets[i] for i in motor1_indices]
                path2 = [targets[i] for i in motor2_indices]
                
                # 模擬執行
                is_safe, total_time, collision_time = self.simulate_parallel_execution(path1, path2)
                
                if is_safe and total_time < best_time:
                    best_time = total_time
                    best_allocation = (path1, path2)
        
        # 如果找不到安全的分配，將所有點分配給馬達1
        if best_allocation is None:
            print("警告：無法找到安全的並行分配，所有點將分配給馬達1")
            best_allocation = (targets, [])
            best_time = self.calculate_path_time(targets, self.motor1_home)
        
        return best_allocation, best_time

    def plan_2(self, targets):
        initA = 30
        initB = 360-30
        FALL_BACK = 15

        wpA_list = []
        wpB_list = []
        wayPoint_list_orig = targets
        wayPoint_list_orig.sort()
        wayPoint_list_orig = [x for x in wayPoint_list_orig if x > initA and x < initB]
        # 去除掉waypoint list orig中相鄰兩點過近的其中的後面的點
        # wayPoint_list_orig = [wayPoint_list_orig[i] for i in range(len(wayPoint_list_orig)) if i == 0 or wayPoint_list_orig[i] - wayPoint_list_orig[i-1] > 15]
        wayPoint_list = [floor(x) for x in wayPoint_list_orig]

        print("valid wayPoints: ", wayPoint_list)
        t = 0
        for i in range(360):
            if (initA in wayPoint_list) and abs(initA - initB) < 20:
                wpA_list.append(initA)
                id = wayPoint_list.index(initA)
                wayPoint_list_orig.pop(id)
                wayPoint_list.pop(id)
                initA -= FALL_BACK
                print(wayPoint_list_orig)
            if (initB in wayPoint_list) and abs(initA - initB) < 20:
                wpA_list.append(initB)
                id = wayPoint_list.index(initB)
                wayPoint_list_orig.pop(id)
                wayPoint_list.pop(id)
                initA -= FALL_BACK
                print(wayPoint_list_orig)
            if initA in wayPoint_list:
                wpA_list.append(initA)
                id = wayPoint_list.index(initA)
                wayPoint_list_orig.pop(id)
                wayPoint_list.pop(id)
                initA -= FALL_BACK
                print(wayPoint_list_orig)
            if initB in wayPoint_list:
                wpB_list.append(initB)
                id = wayPoint_list.index(initB)
                wayPoint_list.pop(id)
                wayPoint_list_orig.pop(id)
                initB += FALL_BACK
                print(wayPoint_list_orig)


            # print(initA, initB, sep='\t')
            initA += 1
            initB -= 1
            t+=1

            if wayPoint_list_orig == []:
                break
        best_allocation = (wpA_list, wpB_list)
        best_time = t
        return best_allocation, best_time

    def optimize_paths(self, targets):
        """
        優化路徑分配
        """
        # return self.plan_1(targets)
        return self.plan_2(targets)


def spDict_to_pathList(spDict:dict):
    if spDict['sp_type'] == "single":
        pathList = spDict['pos_list']
    if spDict['sp_type'] == "multiMotor":
        spDict['pos_list'] = spDict['pos_list_multiMotor']['motor0']+spDict['pos_list_multiMotor']['motor1']
        pathList = spDict['pos_list']
    return pathList, spDict



if __name__ == "__main__":
    testData = [90, 170, 180, 270]
    optimizer = DualMotorPathOptimizer()
    result = optimizer.optimize_paths(testData)
    print(result)