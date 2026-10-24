base_score = 1000

parameters = {
    # infrastructure additions
    "sidewalk": 50,
    "crosswalk": 50,
    "school_zone": 75,
    # infrastructure demerits
    "no_sidewalk": -75,
    "no_crosswalk": -75,
    "highway": -100,
    # risk deductions
    "high_speed": -65,
    "pedestrian_crash": -150,
    "car_crash": -100,
}

def calculate_score(factors: dict): 
    score = base_score

    for factor, value in factors.items():
        if factor and value in parameters:
            score += parameters[factor]

    if score > 1000:
        score = 1000
    elif score < 0:
        score = 0

    return score