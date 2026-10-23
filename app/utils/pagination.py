from flask import request


def paginate(query, per_page=15, page_param="page"):
    page = request.args.get(page_param, 1, type=int)
    page = max(page, 1)
    total = query.count()
    items = query.limit(per_page).offset((page - 1) * per_page).all()
    pages = (total + per_page - 1) // per_page or 1

    class P:
        def __init__(self, items, page, pages, total):
            self.items = items
            self.page = page
            self.pages = pages
            self.total = total
            self.has_prev = page > 1
            self.has_next = page < pages
            self.prev_num = page - 1
            self.next_num = page + 1

    return P(items, page, pages, total)


def apply_search(query, model, term, fields):
    if not term:
        return query
    like = f"%{term}%"
    from sqlalchemy import or_
    return query.filter(or_(*[getattr(model, f).ilike(like) for f in fields]))