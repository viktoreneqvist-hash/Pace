def calculate_average(values: list[float]) -> float:
    if not values:
        raise ValueError("Cannot calculate average of empty list.")

    return sum(values) / len(values)