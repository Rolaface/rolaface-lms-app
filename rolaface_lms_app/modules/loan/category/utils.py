def create_search_filters(search):
    return [
                   ["name", "like", f"%{search}%"],
                   ["loan_category_code", "like", f"%{search}%"],
                   ["loan_category_name", "like", f"%{search}%"]
               ]