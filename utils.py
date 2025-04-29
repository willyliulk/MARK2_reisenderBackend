from itertools import permutations
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


