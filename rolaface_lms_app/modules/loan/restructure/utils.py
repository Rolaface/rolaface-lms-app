def create_search_filters(search):
    return [
                   ["name", "like", f"%{search}%"],
                   ["applicant_type", "like", f"%{search}%"],
                   ["applicant", "like", f"%{search}%"],
                   ["loan", "like", f"%{search}%"],
                   ["loan_product", "like", f"%{search}%"]
               ]