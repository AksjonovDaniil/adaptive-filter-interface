"""
N2 — Lietotāja modelis un lietotāju klases
Autors: Daniils Aksjonovs
Projekts: Adaptīvs filtru interfeiss noliktavas preču uzskaites tabulai

Šī versija izpilda N2 2.–6. sadaļas vajadzības:
- ģenerē sintētisku notikumu žurnālu 30 lietotājiem un 4 sesijām katram;
- izmanto fiksētu seed, lai rezultāts būtu atkārtojams;
- aprēķina 4 lietotāja pazīmes no žurnāla;
- veic normalizāciju, stereotipu un k-vidējo klasifikāciju;
- klasificē jaunus lietotājus;
- demonstrē EMA un histerēzi modelim laikā.

Palaišana:
    python N2_Aksjonovs.py
    python N2_Aksjonovs.py --generate
"""

import csv
import math
import random
import sys
from collections import defaultdict
from pathlib import Path

SEED = 2026
DATA_FILE = Path(__file__).with_name("N2_dati.csv")
SESSIONS_PER_USER = 4

# Trīs sintētiskās lietotāju grupas. Parametri atšķiras no lekcijas parauga.
# time      — vidējais filtra sastādīšanas laiks sekundēs
# p_error   — kļūdas varbūtība vienam filtram
# p_tmpl    — saglabāta šablona izmantošanas varbūtība
# p_complex — salikta filtra (UN/VAI/iekavas) varbūtība
GENERATE_GROUPS = {
    "iesacejs": dict(n=9, time=46, p_error=0.32, p_tmpl=0.04, p_complex=0.10),
    "patstavigais": dict(n=13, time=29, p_error=0.13, p_tmpl=0.30, p_complex=0.38),
    "eksperts": dict(n=8, time=15, p_error=0.04, p_tmpl=0.62, p_complex=0.72),
}

FEATURES = [
    ("x1", "Vidējais filtra sastādīšanas laiks, s"),
    ("x2", "Kļūdas uz 10 filtriem"),
    ("x3", "Šablonu izmantošana, %"),
    ("x4", "Salikto filtru īpatsvars, %"),
]


def generate_log(path: Path, seed: int = SEED) -> int:
    """Ģenerē sintētisku notikumu žurnālu noliktavas filtru sistēmai."""
    rnd = random.Random(seed)
    rows = []
    uid = 0

    for group_name, group in GENERATE_GROUPS.items():
        for _ in range(group["n"]):
            uid += 1
            user_id = f"U{uid:02d}"
            timestamp = 1_788_000_000 + uid * 100_000

            # Katram lietotājam neliela individuālā novirze no grupas vidējā.
            personal = {
                key: group[key] * rnd.uniform(0.75, 1.25)
                for key in ("time", "p_error", "p_tmpl", "p_complex")
            }
            learning_speed = rnd.uniform(0.00, 0.08)

            for session_no in range(1, SESSIONS_PER_USER + 1):
                session_id = f"{user_id}_S{session_no}"
                learning_factor = 1 - learning_speed * (session_no - 1)

                # Vienā sesijā lietotājs izpilda 10–15 filtrus.
                for _ in range(rnd.randint(10, 15)):
                    timestamp += rnd.randint(20, 90)

                    if rnd.random() < personal["p_tmpl"]:
                        rows.append((user_id, session_id, timestamp, "template_used", 1))

                    if rnd.random() < personal["p_error"] * learning_factor:
                        error_type = "syntax_error" if rnd.random() < 0.60 else "semantic_error"
                        rows.append((user_id, session_id, timestamp, error_type, 1))

                    if rnd.random() < personal["p_complex"]:
                        rows.append((user_id, session_id, timestamp, "complex_filter", 1))

                    duration = max(
                        4.0,
                        rnd.gauss(
                            personal["time"] * learning_factor,
                            personal["time"] * 0.18,
                        ),
                    )
                    rows.append((user_id, session_id, timestamp, "filter_run", round(duration, 1)))

    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(["user_id", "session_id", "timestamp", "event_type", "value"])
        writer.writerows(rows)

    return len(rows)


def read_log(path: Path):
    with path.open(encoding="utf-8") as file:
        return list(csv.DictReader(file))


def compute_features(events):
    """Aprēķina x1–x4 no viena lietotāja notikumiem."""
    filter_times = [float(e["value"]) for e in events if e["event_type"] == "filter_run"]
    filter_count = len(filter_times)
    if filter_count == 0:
        return [0.0, 0.0, 0.0, 0.0]

    counts = defaultdict(int)
    for event in events:
        counts[event["event_type"]] += 1

    x1 = sum(filter_times) / filter_count
    x2 = 10 * (counts["syntax_error"] + counts["semantic_error"]) / filter_count
    x3 = 100 * counts["template_used"] / filter_count
    x4 = 100 * counts["complex_filter"] / filter_count

    return [x1, x2, x3, x4]


def features_by_user(log):
    events_by_user = defaultdict(list)
    for event in log:
        events_by_user[event["user_id"]].append(event)
    return {
        user_id: compute_features(events)
        for user_id, events in sorted(events_by_user.items())
    }


def features_by_session(log, user_id):
    """Aprēķina pazīmes katrai konkrētā lietotāja sesijai."""
    events_by_session = defaultdict(list)
    for event in log:
        if event["user_id"] == user_id:
            events_by_session[event["session_id"]].append(event)
    return [
        (session_id, compute_features(events))
        for session_id, events in sorted(events_by_session.items())
    ]


def ema(values, alpha):
    """Eksponenciāli slīdošais vidējais."""
    model = values[0]
    result = [model]
    for value in values[1:]:
        model = alpha * value + (1 - alpha) * model
        result.append(model)
    return result


def hysteresis(session_vectors, centers, start_class, delta=0.1, n_required=2):
    """
    Maina klasi tikai tad, ja cita klase ir tuvāka vismaz par delta
    n_required sesijās pēc kārtas.
    """
    current = start_class
    candidate = None
    streak = 0
    history = []

    for vector in session_vectors:
        best_class, best_distance = nearest(vector, centers)
        current_distance = distance(vector, centers[current])

        if (
            best_class != current
            and best_distance < current_distance - delta
        ):
            if candidate == best_class:
                streak += 1
            else:
                candidate = best_class
                streak = 1

            if streak >= n_required:
                current = best_class
                candidate = None
                streak = 0
        else:
            candidate = None
            streak = 0

        history.append((best_class, current))

    return history


def minmax_params(vectors):
    """Aprēķina min un max katrai pazīmei."""
    columns = list(zip(*vectors))
    mins = [min(column) for column in columns]
    maxs = [max(column) for column in columns]
    return mins, maxs


def normalize(vector, mins, maxs):
    """Min-max normalizācija; ārpus diapazona vērtības ierobežo līdz [0, 1]."""
    normalized = []
    for value, minimum, maximum in zip(vector, mins, maxs):
        if maximum > minimum:
            z = (value - minimum) / (maximum - minimum)
        else:
            z = 0.0
        normalized.append(min(1.0, max(0.0, z)))
    return normalized


# Stereotipu prototipi normalizētajā telpā: x1, x2, x3, x4.
STEREOTYPES = {
    "Iesācējs": [1.0, 1.0, 0.0, 0.0],
    "Patstāvīgais": [0.5, 0.5, 0.5, 0.5],
    "Eksperts": [0.0, 0.0, 1.0, 1.0],
}


def distance(a, b):
    return math.sqrt(sum((x - y) ** 2 for x, y in zip(a, b)))


def nearest(vector, centers):
    items = centers.items() if isinstance(centers, dict) else enumerate(centers)
    return min(((key, distance(vector, center)) for key, center in items), key=lambda item: item[1])


def kmeans(points, k, rnd, max_iter=100):
    centers = [list(p) for p in rnd.sample(points, k)]
    labels = [-1] * len(points)
    for _ in range(max_iter):
        new_labels = [nearest(point, centers)[0] for point in points]
        if new_labels == labels:
            break
        labels = new_labels
        for cluster in range(k):
            members = [point for point, label in zip(points, labels) if label == cluster]
            if members:
                centers[cluster] = [sum(col) / len(members) for col in zip(*members)]
    inertia = sum(distance(point, centers[label]) ** 2 for point, label in zip(points, labels))
    return labels, centers, inertia


def best_kmeans(points, k, runs=10, seed=SEED):
    rnd = random.Random(seed + k)
    candidates = [kmeans(points, k, rnd) for _ in range(runs)]
    return min(candidates, key=lambda result: result[2])


def silhouette_score(points, labels):
    cluster_count = max(labels) + 1
    scores = []
    for i, point in enumerate(points):
        own = [distance(point, other) for j, other in enumerate(points)
               if labels[j] == labels[i] and j != i]
        if not own:
            scores.append(0.0)
            continue
        a = sum(own) / len(own)
        b_values = []
        for cluster in range(cluster_count):
            if cluster == labels[i]:
                continue
            others = [distance(point, other) for j, other in enumerate(points) if labels[j] == cluster]
            if others:
                b_values.append(sum(others) / len(others))
        b = min(b_values)
        scores.append((b - a) / max(a, b) if max(a, b) else 0.0)
    return sum(scores) / len(scores)


def fmt(value, digits=1):
    return f"{value:.{digits}f}".replace(".", ",")


def main():
    if "--generate" in sys.argv or not DATA_FILE.exists():
        event_count = generate_log(DATA_FILE)
        print(f"Ģenerēts {DATA_FILE.name}: {event_count} notikumi, seed = {SEED}")

    log = read_log(DATA_FILE)
    features = features_by_user(log)
    users = list(features)
    session_count = len({event["session_id"] for event in log})

    print(f"Žurnāls: {len(log)} notikumi, {len(users)} lietotāji, {session_count} sesijas")
    print("\nPazīmes pirmajiem 5 lietotājiem:")
    print("Lietotājs\tx1 laiks, s\tx2 kļūdas/10\tx3 šabloni, %\tx4 salikti, %")
    for user_id in users[:5]:
        x1, x2, x3, x4 = features[user_id]
        print(
            f"{user_id}\t\t{fmt(x1)}\t\t{fmt(x2)}\t\t{fmt(x3)}\t\t{fmt(x4)}"
        )

    mins, maxs = minmax_params(list(features.values()))
    print("\nNormalizācijas parametri (min-max):")
    print("Pazīme\tmin\tmax")
    for (code, _), minimum, maximum in zip(FEATURES, mins, maxs):
        print(f"{code}\t{fmt(minimum)}\t{fmt(maximum)}")

    normalized_features = {
        user_id: normalize(vector, mins, maxs)
        for user_id, vector in features.items()
    }

    print("\nStereotipu klasifikācija:")
    stereotype_classes = {
        user_id: nearest(vector, STEREOTYPES)[0]
        for user_id, vector in normalized_features.items()
    }
    for class_name in STEREOTYPES:
        count = sum(1 for value in stereotype_classes.values() if value == class_name)
        print(f"{class_name}: {count} lietotāji")

    points = [normalized_features[user_id] for user_id in users]
    results = {}
    print("\nk-vidējo rezultāti (10 palaišanas katram k):")
    print("k\tsilueta koeficients\tiekšējā novirze")
    for k in (2, 3, 4):
        labels, centers, inertia = best_kmeans(points, k, runs=10)
        silhouette = silhouette_score(points, labels)
        results[k] = (labels, centers, inertia, silhouette)
        print(f"{k}\t{fmt(silhouette, 3)}\t\t{fmt(inertia, 2)}")

    # N2 izvēlamies k = 3, jo tas ļauj veidot trīs jēgpilni atšķirīgus dialogus.
    selected_k = 3
    labels, centers, _, _ = results[selected_k]
    cluster_names = {index: nearest(center, STEREOTYPES)[0] for index, center in enumerate(centers)}

    print("\nIzvēlētās klases (k = 3):")
    print("Klase\tn\tcentrs (x1; x2; x3; x4)")
    for index, center in enumerate(centers):
        class_name = cluster_names[index]
        count = labels.count(index)
        center_text = "; ".join(fmt(value, 2) for value in center)
        print(f"{class_name}\t{count}\t{center_text}")

    kmeans_classes = {
        user_id: cluster_names[label]
        for user_id, label in zip(users, labels)
    }
    differences = [
        user_id for user_id in users
        if stereotype_classes[user_id] != kmeans_classes[user_id]
    ]
    print("\nAtšķirības starp stereotipu un k-vidējo klasifikāciju:")
    if differences:
        for user_id in differences:
            print(f"{user_id}: stereotips = {stereotype_classes[user_id]}, k-vidējo = {kmeans_classes[user_id]}")
    else:
        print("Nav atšķirību.")

    # -----------------------------------------------------------------------
    # 5. Jauna lietotāja klasificēšana
    # -----------------------------------------------------------------------
    # Pazīmju secība: x1 laiks, x2 kļūdas/10, x3 šabloni %, x4 salikti %.
    test_users = {
        "T01": [49.0, 3.5, 4.0, 8.0],
        "T02": [36.0, 1.8, 30.0, 35.0],
        "T03": [14.5, 0.4, 75.0, 85.0],
        "T04": [30.0, 1.2, 40.0, 45.0],
        "T05": [18.0, 0.6, 65.0, 70.0],
    }

    named_centers = {cluster_names[index]: center for index, center in enumerate(centers)}
    print("\nJaunu lietotāju klasificēšana (tuvākais klases centrs):")
    print("Lietotājs\tpazīmes (x1; x2; x3; x4)\tklase\tattālums")
    for test_id, vector in test_users.items():
        normalized = normalize(vector, mins, maxs)
        class_name, d = nearest(normalized, named_centers)
        values = "; ".join(fmt(value, 1) for value in vector)
        print(f"{test_id}\t\t{values}\t{class_name}\t{fmt(d, 2)}")

    # -----------------------------------------------------------------------
    # 6. Modelis laikā: EMA un histerēze
    # -----------------------------------------------------------------------
    ema_user = "U01"
    session_features = features_by_session(log, ema_user)
    # Analizējam x2 — kļūdas uz 10 filtriem.
    error_values = [vector[1] for _, vector in session_features]
    ema_03 = ema(error_values, 0.3)
    ema_06 = ema(error_values, 0.6)

    print(f"\nEMA pazīmei x2 (kļūdas uz 10 filtriem), lietotājs {ema_user}:")
    print("Sesija\tnovērojums\tEMA α=0,3\tEMA α=0,6")
    for index, ((session_id, _), observed, value_03, value_06) in enumerate(
        zip(session_features, error_values, ema_03, ema_06), start=1
    ):
        print(
            f"{index}\t{fmt(observed, 2)}\t\t{fmt(value_03, 2)}\t\t{fmt(value_06, 2)}"
        )

    # U19 ir labs robežgadījums: tuvākā klase mainās no Iesācēja uz
    # Patstāvīgo, un histerēze prasa divas secīgas sesijas pirms maiņas.
    hysteresis_user = "U19"
    h_sessions = features_by_session(log, hysteresis_user)
    h_vectors = [normalize(vector, mins, maxs) for _, vector in h_sessions]
    start_class = nearest(h_vectors[0], named_centers)[0]
    h_history = hysteresis(
        h_vectors, named_centers, start_class, delta=0.1, n_required=2
    )

    print(f"\nHisterēze δ=0,1, N=2, lietotājs {hysteresis_user}:")
    print("Sesija\ttuvākā klase\tpiešķirtā klase")
    for index, (best_class, assigned_class) in enumerate(h_history, start=1):
        print(f"{index}\t{best_class}\t{assigned_class}")


if __name__ == "__main__":
    main()
