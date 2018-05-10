from flask import url_for, abort
from dietrx import app
from math import ceil
from difflib import SequenceMatcher


def search_elastic(index, query, fields, page, per_page):
    body = {'query':{'multi_match': 
    					{
    						'query': str(query), 
    						'fields':fields
    					}
    				},
            'from': (page-1)*per_page,
            'size': per_page
			}
    return app.elasticsearch.search(index=index, doc_type=index, body=body)


def autocomplete_search(index, field, query, separator=False):
    query = query.lower()
    body = {'query': 
				{
                    'wildcard': {str(field): str(query)+'*'}
                }
            }
            
    results = app.elasticsearch.search(index=index, doc_type=index, body=body)
    if separator:
        results = [x['_source'][str(field)].lower() for x in results['hits']['hits']]
        temp = []
        for x in results:
            temp = temp + x.split(separator)
        results = []
        for x in temp:
            if(x.startswith(query)):
                results.append(x)
    else:
        results = [x['_source'][str(field)].lower() for x in results['hits']['hits']]
        temp = []
        for res in results:
            if(res.startswith(query)):
                temp.append(res)
        results = temp
    return list(set(results))



class Pagination(object):

    def __init__(self, page, per_page, results, request, view):
        self.page = page
        self.per_page = per_page
        self.total_count = len(results)


        self.pages = int(ceil(self.total_count / float(self.per_page)))
        self.has_prev = self.page > 1
        self.has_next = self.page < self.pages

        if(self.page <= 0 or self.page > self.pages):
            abort(404)
        
        self.items = results[(page-1)*per_page:page*per_page+1]


        mod_Q = {argf: argv for argf, argv in request.args.items() 
        if argf != 'page'}


        self.first_url = url_for(view, page=1, **mod_Q) \
        if (page != 1) else None
        self.next_url = url_for(view, page=self.page + 1, **mod_Q) \
        if self.has_next else None
        self.prev_url = url_for(view, page=self.page -1, **mod_Q) \
        if self.has_prev else None
        self.last_url = url_for(view, page=self.pages, **mod_Q) \
        if (page != self.pages) else None
