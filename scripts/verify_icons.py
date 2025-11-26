import time

import requests

icons = [
    "laptop",
    "chip",
    "code-tags",
    "robot",
    "brain",
    "cloud",
    "bank",
    "cash",
    "currency-usd",
    "chart-line",
    "trending-up",
    "finance",
    "medical-bag",
    "hospital-box",
    "pill",
    "heart-pulse",
    "dna",
    "flash",
    "oil",
    "solar-power",
    "water",
    "gas-station",
    "lightning-bolt",
    "factory",
    "wrench",
    "cog",
    "package-variant",
    "truck",
    "cart",
    "shopping",
    "food",
    "home",
    "tshirt-crew",
    "phone",
    "antenna",
    "wifi",
    "signal",
    "cellphone",
    "gold",
    "diamond-stone",
    "hammer",
    "barrel",
    "office-building",
    "home-city",
    "domain",
    "power-plug",
    "water-pump",
    "fire",
    "trophy",
    "rocket",
    "target",
    "star",
    "speedometer",
    "database",
    "chart-areaspline",
    "chart-bar",
    "chart-pie",
    "magnify",
    "earth",
    "shield-check",
    "scale-balance",
    "swap-horizontal",
]

valid = []
invalid = []

for icon in icons:
    try:
        response = requests.head(f"https://api.iconify.design/mdi/{icon}.svg", timeout=5)
        if response.status_code == 200:
            valid.append(icon)
        else:
            invalid.append(icon)
    except Exception:
        invalid.append(icon)
    time.sleep(0.1)

print(f"\nVALID ICONS ({len(valid)}/{len(icons)}):")
print(", ".join(valid))
print(f"\nINVALID ICONS ({len(invalid)}):")
print(", ".join(invalid) if invalid else "None - all icons valid!")
