"""
Run once to seed Anton's 5/10/15-year vision goals into the database.
Usage: python seed_vision.py
"""
from database import Database

VISION_GOALS = {
    "5y": [
        "Have one ecom business off the ground, making €50k revenue/month, 25% profit",
        "Living in a house in the center of Poznań: room for each kid, special room with bathroom and jacuzzi, working space, big garage, small workshop",
        "Still have free time — work on average 4h/day",
        "Be healthy and still fit, BJJ black belt and still actively training",
        "Make one big travel a year to a different continent for approx. 2-3 weeks",
        "Speaking Polish fluently (C2)",
    ],
    "10y": [
        "Having sold one business, or growing it further — owning a famous brand throughout Europe",
        "Being a frequently asked speaker for business conferences, having a strong personal brand with a solid following",
        "Still being healthy and fit, working out 6 times/week",
        "Owning a luxury apartment in Świnoujście",
        "Driving Dakar rally with my own team",
    ],
    "15y": [
        "Owning a business which is a market leader throughout Europe — just owning, less managing",
        "Having written a book about branding, marketing, or anything related",
        "Having my children be knowledgeable about business; having the means for them to study further, abroad if necessary",
        "Healthy and fit, working out 6 times/week",
        "Living in a luxury apartment in the center of Poznań or any other interesting city",
    ],
}


def main():
    db = Database()
    total = 0
    for goal_type, goals in VISION_GOALS.items():
        for text in goals:
            db.add_goal(goal_type, text)
            total += 1
            print(f"  [{goal_type}] {text}")
    print(f"\n✅ Seeded {total} vision goals.")


if __name__ == "__main__":
    main()
