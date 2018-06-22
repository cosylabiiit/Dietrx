from flask import url_for, abort
from dietrx import app
from math import ceil
from difflib import SequenceMatcher
from .models import *


def food_chemical(request, NUM_PER_PAGE, page, url, food_id=None, pubchem_id=None):
    q = Food_chemical.query

    if(food_id):
        q = q.filter_by(food_id=food_id)
    elif(pubchem_id):
        q = q.filter_by(pubchem_id=pubchem_id)

    results = q.all()

    results = Pagination(page, NUM_PER_PAGE, results, request, url)

    temp = []

    for res in results.items:
        associations = Food_chemical.query.filter_by(
            pubchem_id=res.pubchem_id, food_id=res.food_id)
        if(food_id):
            temp.append({'chemical': Chemical.query.filter_by(pubchem_id=res.pubchem_id).first(),
                         'associations': associations.first()})
        elif(pubchem_id):
            temp.append({'food': Food.query.filter_by(food_id=res.food_id).first(),
                         'associations': associations.first()})
    results.items = temp

    return results


def disease_chemical(request, NUM_PER_PAGE, page, url, disease_id=None, pubchem_id=None):
    q = Chemical_disease.query

    if(disease_id):
        q = q.filter_by(disease_id=disease_id)
    elif(pubchem_id):
        q = q.filter_by(pubchem_id=pubchem_id)

    results = q.all()

    temp = []
    for res in results:
        via_genes = res.via_genes.split('|')
        temp.append({'association': res,
                     'via_genes': via_genes,
                     'count': len(via_genes)
                     })

    results = sorted(temp, key=lambda x: x['count'], reverse=True)
    results = Pagination(page, NUM_PER_PAGE, results, request, url)

    temp = []

    for res in results.items:
        association = res['association']
        if(len(res['via_genes']) == 1 and res['via_genes'][0] == ''):
            res['via_genes'] = 0
        else:
            res['via_genes'] = len(res['via_genes'])
        temp.append({'chemical': association.chemical,
                     'disease': association.disease,
                     'association': association,
                     'via_genes': res['via_genes'],
                     })

    results.items = temp
    return results


def chemical_gene(request, NUM_PER_PAGE, page, url, gene_id=None, pubchem_id=None):
    q = Chemical_gene.query
    if(pubchem_id):
        q = q.filter_by(pubchem_id=pubchem_id)
    elif(gene_id):
        q = q.filter_by(gene_id=gene_id)

    results = q.all()

    temp = []
    for res in results:
        via_diseases = [] if (res.via_diseases == '') else res.via_diseases.split('|')
        temp.append({'association': res,
                     'via_diseases': via_diseases,
                     'count': len(via_diseases)
                     })

    results = sorted(temp, key=lambda x: x['count'], reverse=True)
    results = Pagination(page, NUM_PER_PAGE, results, request, url)

    temp = []

    for res in results.items:
        association = res['association']
        if(len(res['via_diseases']) == 1 and res['via_diseases'][0] == ''):
            res['via_diseases'] = 0
        else:
            res['via_diseases'] = len(res['via_diseases'])
        temp.append({'chemical': association.chemical,
                     'gene': association.gene,
                     'association': association,
                     'via_diseases': res['via_diseases'],
                     })

    results.items = temp
    return results


def food_gene(request, NUM_PER_PAGE, page, url, gene_id=None, food_id=None):
    q = Food_gene.query
    if(food_id):
        q = q.filter_by(food_id=food_id)
    elif(gene_id):
        q = q.filter_by(gene_id=gene_id)

    results = q.all()

    temp = []
    for res in results:
        disease_ids = [] if (res.via_diseases == '') else res.via_diseases.split('|')
        pubchem_ids = [] if (res.via_chemicals == '') else res.via_chemicals.split('|')
        temp.append({'association': res,
                     'via_diseases': disease_ids,
                     'via_chemicals': pubchem_ids,
                     'count': len(disease_ids) + len(pubchem_ids)})

    results = sorted(temp, key=lambda x: x['count'], reverse=True)
    results = Pagination(page, NUM_PER_PAGE, results, request, url)

    temp = []

    for res in results.items:
        association = res['association']
        temp.append({'gene': association.gene,
                     'food': association.food,
                     'associations': association,
                     'via_diseases': res['via_diseases'],
                     'via_chemicals': res['via_chemicals'],
                     })

    results.items = temp
    return results


def disease_gene(request, NUM_PER_PAGE, page, url, gene_id=None, disease_id=None):

    q = Disease_gene.query
    if(disease_id):
        q = q.filter_by(disease_id=disease_id)
    elif(gene_id):
        q = q.filter_by(gene_id=gene_id)

    results = q.all()

    temp = []
    for res in results:
        via_chemicals = [] if (res.via_chemicals == '') else res.via_chemicals.split('|')
        temp.append({'association': res,
                     'via_chemicals': via_chemicals,
                     'count': len(via_chemicals)})
    results = sorted(temp, key=lambda x: x['count'], reverse=True)
    results = Pagination(page, NUM_PER_PAGE, results, request, url)

    temp = []

    for res in results.items:
        association = res['association']
        if(len(res['via_chemicals']) == 1 and res['via_chemicals'][0] == ''):
            res['via_chemicals'] = 0
        else:
            res['via_chemicals'] = len(res['via_chemicals'])
        temp.append({'gene': association.gene,
                     'disease': association.disease,
                     'association': association,
                     'reference': association.reference,
                     'via_chemicals': res['via_chemicals'],
                     })

    results.items = temp

    return results


def search_elastic(index, query, fields, page, per_page):
    body = {'query': {'multi_match':
                      {
                          'query': str(query),
                          'fields': fields
                      }
                      },
            'from': (page - 1) * per_page,
            'size': per_page
            }
    return app.elasticsearch.search(index=index, doc_type=index, body=body)


def autocomplete_search(index, field, query, separator=False):
    query = query.lower()
    body = {'query':
            {
                'wildcard': {str(field): str(query) + '*'}
            }
            }

    results = app.elasticsearch.search(index=index, doc_type=index, body=body)
    if separator:
        results = [x['_source'][str(field)].lower()
                   for x in results['hits']['hits']]
        temp = []
        for x in results:
            temp = temp + x.split(separator)
        results = []
        for x in temp:
            if(x.startswith(query)):
                results.append(x)
    else:
        results = [x['_source'][str(field)].lower()
                   for x in results['hits']['hits']]
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

        self.items = results[(page - 1) * per_page:page * per_page + 1]

        mod_Q = {argf: argv for argf, argv in request.args.items()
                 if argf != 'page'}

        self.first_url = url_for(view, page=1, **mod_Q) \
            if (page != 1) else None
        self.next_url = url_for(view, page=self.page + 1, **mod_Q) \
            if self.has_next else None
        self.prev_url = url_for(view, page=self.page - 1, **mod_Q) \
            if self.has_prev else None
        self.last_url = url_for(view, page=self.pages, **mod_Q) \
            if (page != self.pages) else None
