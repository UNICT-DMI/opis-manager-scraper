from src.api_client import get_departments


def main():
    print("Avvio scraper OPIS...")

    anno_target = 2023
    print(f"Scarico i dipartimenti per l'anno {anno_target}...")

    departments = get_departments(anno_target)

    print(f"Trovati {len(departments)} dipartimenti.")

    # Stampiamo i primi 3 per verifica
    for dip in departments[:3]:
        print(f"- [{dip.unict_id}] {dip.nome} ({dip.anno_accademico})")


if __name__ == "__main__":
    main()
