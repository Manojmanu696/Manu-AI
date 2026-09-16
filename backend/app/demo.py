from .models import MediaItem, Memory

DEMO_MEDIA = [
    {"media_type":"movie","title":"Arrival","genres":"Science Fiction, Drama","personal_rating":9,"sentiment":"like","status":"completed","runtime":"116 min","release_year":2016,"description":"A linguist tries to understand visitors from another world.","tags":"thoughtful, first contact"},
    {"media_type":"movie","title":"The Prestige","genres":"Mystery, Thriller","personal_rating":9,"sentiment":"like","status":"completed","runtime":"130 min","release_year":2006,"description":"Two rival magicians take obsession to dangerous limits.","tags":"twisty, psychological"},
    {"media_type":"anime","title":"Monster","genres":"Psychological, Mystery","personal_rating":9,"sentiment":"like","status":"completed","runtime":"74 episodes","release_year":2004,"description":"A surgeon pursues the patient whose life he saved.","tags":"slow burn, moral ambiguity"},
    {"media_type":"anime","title":"Frieren: Beyond Journey's End","genres":"Fantasy, Drama","personal_rating":None,"sentiment":"neutral","status":"want","runtime":"28 episodes","release_year":2023,"description":"An elf mage reflects on friendship after an adventure ends.","tags":"reflective"},
    {"media_type":"tv","title":"Severance","genres":"Science Fiction, Thriller","personal_rating":8.5,"sentiment":"like","status":"current","runtime":"45 min episodes","release_year":2022,"description":"Workers split their work and home memories.","tags":"high concept, mystery"},
    {"media_type":"game","title":"Outer Wilds","genres":"Adventure, Mystery","personal_rating":10,"sentiment":"like","status":"completed","runtime":"16–20 hours","release_year":2019,"description":"Explore a handcrafted solar system caught in a time loop.","tags":"discovery, space"},
    {"media_type":"game","title":"Disco Elysium","genres":"RPG, Mystery","personal_rating":None,"sentiment":"neutral","status":"want","runtime":"25–40 hours","release_year":2019,"description":"A detective rebuilds himself while solving a murder.","tags":"writing, choices"},
    {"media_type":"book","title":"Piranesi","genres":"Fantasy, Mystery","personal_rating":8.5,"sentiment":"like","status":"completed","runtime":"272 pages","release_year":2020,"description":"A man lives in an infinite house of statues and tides.","tags":"atmospheric, uncanny"},
    {"media_type":"book","title":"Project Hail Mary","genres":"Science Fiction, Adventure","personal_rating":None,"sentiment":"neutral","status":"want","runtime":"496 pages","release_year":2021,"description":"A lone astronaut must save humanity.","tags":"science, space"},
]

DEMO_MEMORIES = [
    {"category":"favorite genres","content":"Psychological mysteries and smart science fiction.","source":"user"},
    {"category":"preferred pacing","content":"Likes deliberate stories when the payoff is meaningful.","source":"user"},
    {"category":"favorite themes","content":"Identity, moral ambiguity, discovery, and human connection.","source":"inferred","confidence":0.78},
]


def load_demo(db):
    if db.query(MediaItem).filter_by(is_demo=True).first():
        return False
    for item in DEMO_MEDIA:
        db.add(MediaItem(**item, is_demo=True))
    for memory in DEMO_MEMORIES:
        db.add(Memory(**memory, is_demo=True))
    db.commit()
    return True
