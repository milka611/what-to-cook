
import streamlit as st
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import json
import re

st.set_page_config(
    page_title="Что приготовить?",
    page_icon="🍳"
)

# =====================================
# 1. СОХРАНЁННЫЕ РЕЦЕПТЫ
# =====================================

# Резервная учебная база.
# Состав ингредиентов может отличаться
# от актуальной версии сайта.

RECIPES = [
    {
        "name": "Бутерброды с беконом и сыром",
        "ingredients": [
            "Хлеб", "Бекон", "Помидоры",
            "Листья салата", "Творожный сыр",
            "Горчица"
        ],
        "url": "https://1000.menu/cooking/84615-buterbrody-s-bekonom-i-syrom"
    },
    {
        "name": "Салат с помидорами, сыром и яйцами",
        "ingredients": [
            "Помидоры", "Майонез", "Чеснок",
            "Твёрдый сыр", "Соль", "Яйца"
        ],
        "url": "https://1000.menu/cooking/44402-salat-s-pomidorami-syrom-yaicami"
    },
    {
        "name": "Бутерброды с помидорами и сыром",
        "ingredients": [
            "Батон", "Помидоры", "Твёрдый сыр",
            "Чеснок", "Майонез"
        ],
        "url": "https://1000.menu/cooking/58752-buterbrody-s-pomidorami-i-syrom"
    },
    {
        "name": "Омлет с сыром и молоком",
        "ingredients": [
            "Молоко", "Твёрдый сыр", "Яйца",
            "Сливочное масло", "Соль"
        ],
        "url": "https://1000.menu/cooking/34604-omlet-s-syrom-na-skovorode-s-molokom-pyshnyi"
    },
    {
        "name": "Лаваш с сыром и помидорами",
        "ingredients": [
            "Лаваш", "Твёрдый сыр",
            "Помидоры", "Яйца",
            "Растительное масло", "Соль"
        ],
        "url": "https://1000.menu/cooking/49491-lavash-s-syrom-i-pomidorami-na-skovorode"
    },
    {
        "name": "Бутерброды с творожным сыром",
        "ingredients": [
            "Хлеб", "Творожный сыр",
            "Вяленые помидоры", "Базилик"
        ],
        "url": "https://1000.menu/cooking/84822-tvorojnyi-syr-s-vyalenymi-pomidorami"
    }
]

# =====================================
# 2. ПОДБОРКИ ДЛЯ ОНЛАЙН-ПОИСКА
# =====================================

CATALOGS = {
    "Яйца": "https://1000.menu/catalog/zavtrak-iz-yaic",
    "Хлеб": "https://1000.menu/catalog/buterbrodj",
    "Бекон": "https://1000.menu/catalog/buterbrodj",
    "Авокадо": "https://1000.menu/catalog/buterbrody-na-zavtrak"
}

# =====================================
# 3. СИНОНИМЫ
# =====================================

ALIASES = {
    "яйцо": "яйца",
    "куриные яйца": "яйца",
    "яйцо куриное": "яйца",
    "яйца": "яйца",

    "сыр": "сыр",
    "твердый сыр": "сыр",
    "твёрдый сыр": "сыр",

    "картошка": "картофель",
    "картофель": "картофель",

    "помидор": "помидоры",
    "помидоры черри": "помидоры",
    "томаты": "помидоры",
    "помидоры": "помидоры",

    "батон": "хлеб",
    "белый хлеб": "хлеб",
    "черный хлеб": "хлеб",
    "чёрный хлеб": "хлеб",
    "хлеб": "хлеб",

    "салат": "листья салата",
    "листья салата": "листья салата",

    "лаваш тонкий": "лаваш",
    "лаваш": "лаваш",

    "куриное филе": "курица",
    "куриная грудка": "курица",
    "курица": "курица"
}


def normalize(product):
    text = str(product).strip().casefold()
    text = text.replace("ё", "е")
    text = re.sub(r"\s+", " ", text)

    aliases = {
        key.replace("ё", "е"): value.replace("ё", "е")
        for key, value in ALIASES.items()
    }

    return aliases.get(text, text)


# =====================================
# 4. ПАМЯТЬ ПРИЛОЖЕНИЯ
# =====================================

if "cart" not in st.session_state:
    st.session_state.cart = []

if "results" not in st.session_state:
    st.session_state.results = None

if "search_info" not in st.session_state:
    st.session_state.search_info = ""


def reset_search():
    st.session_state.results = None
    st.session_state.search_info = ""


def add_product(product):
    product = product.strip()

    if not product:
        return False

    existing = {
        normalize(p) for p in st.session_state.cart
    }

    if normalize(product) in existing:
        return False

    st.session_state.cart.append(product)
    reset_search()
    return True


# =====================================
# 5. СРАВНЕНИЕ РЕЦЕПТОВ
# =====================================

def compare_recipe(recipe, cart):
    cart_set = {normalize(p) for p in cart}

    available = []
    missing = []

    for ingredient in recipe["ingredients"]:
        if normalize(ingredient) in cart_set:
            available.append(ingredient)
        else:
            missing.append(ingredient)

    total = len(recipe["ingredients"])

    percent = round(
        len(available) / total * 100
    ) if total else 0

    return {
        **recipe,
        "available": available,
        "missing": missing,
        "percent": percent,
        "matched": len(available),
        "total": total
    }


def rank_recipes(recipes, cart):
    results = []

    seen = set()

    for recipe in recipes:
        url = recipe["url"]

        if url in seen:
            continue

        seen.add(url)

        result = compare_recipe(recipe, cart)

        if result["matched"] > 0:
            results.append(result)

    results.sort(
        key=lambda r: (
            r["percent"],
            r["matched"]
        ),
        reverse=True
    )

    return results


# =====================================
# 6. ЗАГРУЗКА HTML
# =====================================

@st.cache_data(ttl=600)
def get_page(url):
    response = requests.get(
        url,
        timeout=15,
        headers={
            "User-Agent": "Mozilla/5.0"
        }
    )

    response.raise_for_status()

    return BeautifulSoup(
        response.text,
        "html.parser"
    )


# =====================================
# 7. ССЫЛКИ НА РЕЦЕПТЫ
# =====================================

def collect_links(catalog_url):
    soup = get_page(catalog_url)

    links = []

    for a in soup.find_all("a", href=True):
        full_url = urljoin(
            catalog_url,
            a["href"]
        )

        parsed = urlparse(full_url)

        if parsed.hostname not in (
            "1000.menu",
            "www.1000.menu"
        ):
            continue

        if not re.match(
            r"^/cooking/\d+-",
            parsed.path
        ):
            continue

        clean_url = (
            "https://1000.menu" + parsed.path
        )

        if clean_url not in links:
            links.append(clean_url)

        if len(links) >= 12:
            break

    return links


# =====================================
# 8. ИЗВЛЕЧЕНИЕ ИНГРЕДИЕНТОВ
# =====================================

def find_recipe_json(data):
    if isinstance(data, list):
        for item in data:
            found = find_recipe_json(item)
            if found:
                return found

    if isinstance(data, dict):
        types = data.get("@type", [])

        if isinstance(types, str):
            types = [types]

        if "Recipe" in types:
            return data

        for value in data.values():
            if isinstance(value, (list, dict)):
                found = find_recipe_json(value)
                if found:
                    return found

    return None


def read_recipe(url):
    soup = get_page(url)

    title = (
        soup.h1.get_text(" ", strip=True)
        if soup.h1 else "Без названия"
    )

    ingredients = []

    # Первый способ — JSON-LD
    for script in soup.find_all(
        "script",
        type="application/ld+json"
    ):
        try:
            data = json.loads(
                script.string or ""
            )
        except (ValueError, TypeError):
            continue

        recipe_data = find_recipe_json(data)

        if recipe_data:
            title = recipe_data.get(
                "name", title
            )

            raw = recipe_data.get(
                "recipeIngredient", []
            )

            if isinstance(raw, str):
                raw = [raw]

            ingredients = [
                str(item).strip()
                for item in raw
                if str(item).strip()
            ]

            if ingredients:
                break

    # Второй способ — HTML
    if not ingredients:
        for element in soup.select(
            '[itemprop="recipeIngredient"]'
        ):
            text = element.get_text(
                " ", strip=True
            )

            if text:
                ingredients.append(text)

    # Третий способ — ссылки в разделе
    # с заголовком "Ингредиенты"
    if not ingredients:
        heading = soup.find(
            re.compile(r"^h[1-6]$"),
            string=re.compile(
                "Ингредиенты",
                re.IGNORECASE
            )
        )

        if heading:
            for element in heading.next_elements:
                if getattr(element, "name", None) in (
                    "h1", "h2", "h3"
                ):
                    break

                if getattr(element, "name", None) == "a":
                    href = element.get("href", "")

                    if re.match(
                        r"^/(?:products|ingredient|ingredients)/",
                        href
                    ):
                        name = element.get_text(
                            " ", strip=True
                        )

                        if name:
                            ingredients.append(name)

    ingredients = list(
        dict.fromkeys(ingredients)
    )

    if not ingredients:
        return None

    return {
        "name": title,
        "ingredients": ingredients,
        "url": url,
        "source": "online"
    }


# =====================================
# 9. ОНЛАЙН-ПОИСК
# =====================================

def search_online(cart):
    catalog_urls = []
    cart_set = {normalize(p) for p in cart}

    for product, url in CATALOGS.items():
        if normalize(product) in cart_set:
            if url not in catalog_urls:
                catalog_urls.append(url)

    if not catalog_urls:
        catalog_urls = [
            "https://1000.menu/catalog/zavtrak-iz-yaic",
            "https://1000.menu/catalog/buterbrodj"
        ]

    all_links = []

    for catalog in catalog_urls:
        try:
            links = collect_links(catalog)

            for link in links:
                if link not in all_links:
                    all_links.append(link)

        except requests.RequestException:
            continue

    # Ограничиваем количество запросов
    all_links = all_links[:20]

    online_recipes = []

    for link in all_links:
        try:
            recipe = read_recipe(link)

            if recipe:
                online_recipes.append(recipe)

        except (
            requests.RequestException,
            ValueError
        ):
            continue

    return online_recipes


# =====================================
# 10. ИНТЕРФЕЙС
# =====================================

st.title("🍳 Что приготовить?")

st.write(
    "Выберите продукты, которые есть дома, "
    "и найдите подходящие рецепты."
)

PRODUCTS = [
    "Яйца", "Сыр", "Помидоры",
    "Огурцы", "Картофель", "Хлеб",
    "Курица", "Молоко", "Бекон",
    "Салат", "Творожный сыр",
    "Лаваш", "Авокадо", "Лук",
    "Чеснок", "Майонез",
    "Растительное масло",
    "Сливочное масло", "Соль",
    "Перец", "Горчица", "Зелень"
]

selected = st.multiselect(
    "🧺 Выберите продукты",
    PRODUCTS
)

if st.button("➕ Добавить выбранные продукты"):
    count = 0

    for product in selected:
        if add_product(product):
            count += 1

    st.success(f"Добавлено продуктов: {count}")


custom = st.text_input(
    "✏️ Введите свой продукт"
)

if st.button("➕ Добавить свой продукт"):
    if add_product(custom):
        st.success("Продукт добавлен!")
    else:
        st.warning(
            "Введите продукт, которого нет в корзине."
        )


# =====================================
# 11. КОРЗИНА
# =====================================

st.subheader("🧺 Ваша корзина")

if st.session_state.cart:

    for product in st.session_state.cart:
        col1, col2 = st.columns([4, 1])

        with col1:
            st.write("•", product)

        with col2:
            if st.button(
                "❌",
                key=f"delete_{product}"
            ):
                st.session_state.cart.remove(product)
                reset_search()
                st.rerun()

    if st.button("🗑️ Очистить корзину"):
        st.session_state.cart = []
        reset_search()
        st.rerun()

    st.divider()

    # =================================
    # 12. РЕЖИМ ПОИСКА
    # =================================

    mode = st.radio(
        "Как искать рецепты?",
        [
            "Быстрый поиск (сохранённые)",
            "Онлайн + сохранённые"
        ]
    )

    if st.button(
        "🔎 Найти рецепты",
        type="primary"
    ):

        if mode == "Быстрый поиск (сохранённые)":
            combined = [
                {**r, "source": "saved"}
                for r in RECIPES
            ]

            st.session_state.search_info = (
                "Поиск выполнен по сохранённому каталогу."
            )

        else:
            with st.spinner(
                "Загружаем рецепты с 1000.menu..."
            ):
                online = search_online(
                    st.session_state.cart
                )

            # Если один рецепт есть в обоих
            # каталогах, онлайн-версия
            # имеет приоритет
            combined_map = {
                r["url"]: {**r, "source": "saved"}
                for r in RECIPES
            }

            for recipe in online:
                combined_map[recipe["url"]] = recipe

            combined = list(
                combined_map.values()
            )

            st.session_state.search_info = (
                f"Автоматически прочитано рецептов: "
                f"{len(online)}. "
                f"Всего в объединённом каталоге: "
                f"{len(combined)}."
            )

        st.session_state.results = rank_recipes(
            combined,
            st.session_state.cart
        )

    # =================================
    # 13. РЕЗУЛЬТАТЫ
    # =================================

    if st.session_state.results is not None:

        results = st.session_state.results

        st.subheader("🍽️ Найденные рецепты")

        st.caption(
            st.session_state.search_info
        )

        st.write(
            f"Подходящих рецептов: {len(results)}"
        )

        filter_mode = st.radio(
            "Фильтр",
            [
                "Все подходящие",
                "Можно приготовить сейчас",
                "Не хватает ингредиентов"
            ]
        )

        if filter_mode == "Можно приготовить сейчас":
            displayed = [
                r for r in results
                if not r["missing"]
            ]

        elif filter_mode == "Не хватает ингредиентов":
            displayed = [
                r for r in results
                if r["missing"]
            ]

        else:
            displayed = results

        limit = st.slider(
            "Сколько рецептов показать?",
            min_value=1,
            max_value=30,
            value=10
        )

        displayed = displayed[:limit]

        if not displayed:
            st.info(
                "По этому фильтру рецептов пока нет."
            )

        for recipe in displayed:

            with st.container(border=True):

                st.subheader(recipe["name"])

                if recipe["source"] == "online":
                    st.caption(
                        "🌐 Данные загружены с сайта"
                    )
                else:
                    st.caption(
                        "📚 Сохранённый рецепт"
                    )

                st.progress(
                    recipe["percent"] / 100
                )

                st.write(
                    f"Совпадение: {recipe['percent']}% "
                    f"({recipe['matched']} из "
                    f"{recipe['total']})"
                )

                st.success(
                    "✅ Есть: " +
                    ", ".join(recipe["available"])
                )

                if recipe["missing"]:
                    st.warning(
                        "🛒 Не хватает: " +
                        ", ".join(recipe["missing"])
                    )
                else:
                    st.success(
                        "🎉 Все ингредиенты есть!"
                    )

                st.link_button(
                    "📖 Открыть рецепт",
                    recipe["url"]
                )

        st.caption(
            "Процент показывает совпадение названий "
            "ингредиентов, а не их количества. "
            "Сохранённые рецепты могут содержать "
            "неполный или устаревший состав."
        )

else:
    st.info(
        "Корзина пока пуста. Добавьте продукты!"
    )
