safety_score = 1000

def infrastructure_score(
    no_sidewalk,
    no_crosswalk,
    highway,
    sidewalk,
    crosswalk,
    no_highway,
    school_zone
):
    return safety_score + infrastructure_score

def potential_danger_score(
    high_speed_limit,
    heavy_traffic,
    pedestrian_crashes,
    car_crashes,
):
    return potential_danger_score + safety_score