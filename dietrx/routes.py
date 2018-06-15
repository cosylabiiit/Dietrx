from dietrx import app, fgname2id
from flask import request, render_template, url_for, redirect, abort, Response, jsonify
from pybel import readstring
from .models import *
import json
from .util import Pagination, autocomplete_search, search_elastic
from .forms import ChemicalSearchForm
from subprocess import check_call
from pybel import readfile
import numpy as np

NUM_PER_PAGE = 10
NUM_PER_PAGE_CHEM = 100

@app.route('/dietrx/', methods=['GET'])
@app.route('/dietrx/index', methods=['GET'])
def index():
    chemical_search_form = ChemicalSearchForm()
    return render_template('search/search.html',
                           chemical_search_form=chemical_search_form)


@app.route('/dietrx/search', methods=['GET'])
def search():
    table = request.args.get('table')
    query = request.args.get('query')

    page = request.args.get('page', 1, type=int)
    template = ''
    if(table == 'food'):
        results = search_elastic(table, query, Food.__searchable__, page, NUM_PER_PAGE)
        template = 'food/search_results.html'
    elif(table == 'disease'):
        results = search_elastic(table, query, Disease.__searchable__, page, NUM_PER_PAGE)
        template = 'disease/search_results.html'
    elif(table == 'gene'):
        results = search_elastic(table, query, Gene.__searchable__, page, NUM_PER_PAGE)
        template = 'gene/search_results.html'
    else:
        abort(404)

    page_data = Pagination(page, NUM_PER_PAGE, [0]*results['hits']['total'], request, 'search') 

    return render_template(template, 
                           results=results,
                           next_url=page_data.next_url,
                           last_url=page_data.last_url,
                           prev_url=page_data.prev_url,
                           first_url=page_data.first_url,
                           has_next=page_data.has_next,
                           has_prev=page_data.has_prev,
                           page_number=page_data.page,
                           total_pages=page_data.pages)



def find_similar(smiles):
    """ Runs a shell command to find similar molecules given
    a query molecule """

    # Run shell command to find similar molecules and get results
    check_call(['babel', 'allmol.fs', 'temp/results.sdf',
                '-s' + smiles, '-at0.4'],
               cwd='dietrx/static')

    results = readfile('sdf', 'dietrx/static/temp/results.sdf')

    # Get molecule objects from results
    mol_ids = [mol.data['pubchem_id'] for mol in results]

    return mol_ids



def process_search_query(formdata):

    # Make a query dictionary
    search_by_smiles = False

    # Common identifiers / ids.
    results = Chemical.query.filter()
    for field in ['common_name', 'iupac_name', 'pubchem_id']:
        key = formdata.get(field).strip()

        if key:
            results = results.filter(getattr(Chemical, field).ilike(key))

    # Functional group
    if formdata.get('functional_group'):
        try:
            fgid = fgname2id[formdata.get('functional_group').lower().strip()]
        except KeyError:
            fgid = len(fgname2id) + 1

        results = results.filter(Chemical.functional_group_idx.contains(fgid))

    # Molecular properties.
    for field in ['molecular_weight', 'hba_count', 'hbd_count', 'num_rings',
                  'num_rotatablebonds', 'number_of_aromatic_bonds', 'alogp']:
        if formdata.get(field):
            field_query = formdata.get(field).strip()

            if ':' in field_query:
                low, high = field_query.split(':')

                results = results.filter((getattr(Chemical, field) >= float(low)) & (
                    getattr(Chemical, field) <= float(high)))
            else:
                results = results.filter_by(**{field: float(field_query)})

    # Filter data further based on similarity coefficient
    if formdata.get('smiles'):
        smiles = formdata.get('smiles').strip()
        mol_ids = find_similar(smiles)
        print(len(mol_ids))
        results = results.filter(Chemical.pubchem_id.in_(mol_ids))
        search_by_smiles = True

    return results, search_by_smiles


@app.route('/dietrx/chemical_search', methods=['GET'])
def chemical_search():
    results, search_by_smiles = process_search_query(
        request.args)

    # Paginate results
    # page = request.args.get('page', type=int) \
    #     if (request.args.get('page') is not None) else 1
    page = request.args.get('page', 1, type=int)

    # Remove page from query
    mod_Q = {argf: argv for argf, argv in request.args.items()
             if argf != 'page'}

    # Create a pagination object from results
    paginated_results = results.paginate(page, NUM_PER_PAGE_CHEM, False)

    # If similarity search, pagination object is just a convenience wrapper.
    if search_by_smiles:
        res_items = results.all()
        fps = [readstring("smi", res.smiles).calcfp()
               for res in res_items]
        query_fp = readstring("smi", request.args.get('smiles')).calcfp()
        sim_coeffs = [np.round(query_fp | fp, 2) for fp in fps]
        rsim = sorted(zip(res_items, sim_coeffs), key=lambda k: k[1])[
            ::-1][(page - 1) * NUM_PER_PAGE_CHEM: page * NUM_PER_PAGE_CHEM]
        res_items = [r for r, sim in rsim]
        sim_coeffs = [sim for r, sim in rsim]
    else:
        res_items = paginated_results.items
        sim_coeffs = [0] * NUM_PER_PAGE_CHEM

    first_url = url_for('chemical_search', page=1, **mod_Q) \
        if (page != 1) else None
    next_url = url_for('chemical_search', page=paginated_results.next_num, **mod_Q) \
        if paginated_results.has_next else None
    prev_url = url_for('chemical_search', page=paginated_results.prev_num, **mod_Q) \
        if paginated_results.has_prev else None
    last_url = url_for('chemical_search', page=paginated_results.pages, **mod_Q) \
        if (page != paginated_results.pages) else None

    return render_template('chemical/chemical_search_results.html',
                           results=zip(res_items, sim_coeffs),
                           search_by_smiles=search_by_smiles,
                           first_url=first_url, next_url=next_url,
                           prev_url=prev_url, last_url=last_url,
                           request=request, page=page,
                           total_pages=paginated_results.pages)


@app.route('/dietrx/chemical_advanced_search', methods=['GET'])
def chemical_advanced_search():
    chemical_search_form = ChemicalSearchForm()
    return render_template('chemical/chemical_advanced_search.html',
                           chemical_search_form=chemical_search_form,
                           advanced_search=True)


@app.route('/dietrx/autocomplete', methods=['GET'])
def autocomplete():
    query = request.args.get('query')
    table = str(request.args.get('table'))

    results = []
    if(table == 'food'):
        for column in ['display_name', 'food_category', 'common_names']:
            if(column in Food.__separators__):
                results = results + autocomplete_search(table, column, query, Food.__separators__[column])
            else:               
                results = results + autocomplete_search(table, column, query)
    elif(table == 'disease'):
        for column in ['disease_name', 'disease_category', 'disease_synonyms']:
            if(column in Disease.__separators__):
                results = results + autocomplete_search(table, column, query, Disease.__separators__[column])
            else:               
                results = results + autocomplete_search(table, column, query)
    elif(table == 'gene'):
        for column in Gene.__searchable__:
            if(column in Gene.__separators__):
                results = results + autocomplete_search(table, column, query, Gene.__separators__[column])
            else:               
                results = results + autocomplete_search(table, column, query)
    else:
        abort(404)
    
    results = list(set(results))
    return jsonify(json.dumps(results))


@app.route('/dietrx/get_associations', methods=['GET'])
def get_associations():
    if (not request.args.get('food_id')) or (not request.args.get('disease_id')):
        return redirect(url_for('index'))
    
    food_id = request.args.get('food_id')
    disease_id = request.args.get('disease_id')

    food = Food.query.filter_by(food_id=food_id).first()
    disease = Disease.query.filter_by(disease_id=disease_id).first()

    if (food is None) or (disease is None):
        abort(404)
    
    associations = Food_disease.query.filter_by(disease_id=disease_id, food_id=food_id)
    
    q = db.session.query(Chemical)\
                .filter(Food_chemical.food_id == food_id)\
                .filter(Chemical_disease.disease_id == disease_id)\
                .filter(Food_chemical.pubchem_id == Chemical.pubchem_id,
                        Chemical_disease.pubchem_id == Chemical.pubchem_id)
    result = {'disease': disease,
            'food': food,
            'positive_associations': associations.filter_by(association='positive').all(),
            'negative_associations': associations.filter_by(association='negative').all(),
            'inference_network': q.all()}

    return render_template('common/associations_popup.html', result = result)


@app.route('/dietrx/get_food', methods=['GET'])
def get_food():
    if not request.args.get('food_id'):
        return redirect(url_for('index'))

    food_id = request.args.get('food_id')
    food = Food.query.filter_by(food_id=food_id).first()

    page = request.args.get('page', 1, type=int)


    if (food is not None):

        subcategory_that_exist = []
        if(len(food.food_disease) != 0):
            subcategory_that_exist.append('disease')
        if(len(food.food_gene) != 0):
            subcategory_that_exist.append('gene')
        if(len(food.food_chemical) != 0):
            subcategory_that_exist.append('chemical')
        if(len(subcategory_that_exist)==0):
            abort(404)
        subcategory = request.args.get('subcategory', subcategory_that_exist[0])

        if(subcategory == 'disease'):

            results = db.session.query(Food_disease.disease_id, 
                            db.func.count(Food_disease.disease_id).label('total'))\
                            .filter_by(food_id=food_id).group_by(Food_disease.disease_id)\
                            .order_by('total DESC').all()

            results = Pagination(page, NUM_PER_PAGE, results, request, 'get_food')

            temp = []

            for res in results.items:
                temp.append({'disease': Disease.query.filter_by(disease_id = res.disease_id).first(),
                            'positive_associations': Food_disease.query.filter_by(food_id=food_id, disease_id=res.disease_id, association='positive').all(),
                            'negative_associations': Food_disease.query.filter_by(food_id=food_id, disease_id=res.disease_id, association='negative').all()})


            results.items = temp
            
        elif(subcategory == 'gene'):

            results = Food_gene.query.filter_by(food_id=food_id).all()

            temp = []
            for res in results:
                temp.append({'association': res,
                            'count': len(res.inference_network.split('|'))})
            
            results = sorted(temp, key=lambda x:x['count'], reverse=True)
            results = Pagination(page, NUM_PER_PAGE, results, request, 'get_food')

            temp = []

            for res in results.items:
                association = res['association']
                ids = association.inference_network.split('|')
                diseases = Disease.query.filter(Disease.disease_id.in_(ids)).all()
                temp.append({'gene': association.gene, 
                            'associations': association,
                            'diseases': diseases,
                            'num_of_diseases': res['count']})


            results.items = temp
            
        elif(subcategory == 'chemical'):

            results = db.session.query(Food_chemical.pubchem_id,
                              db.func.count(Food_chemical.pubchem_id).label('total'))\
                            .filter_by(food_id=food_id).group_by(Food_chemical.pubchem_id)\
                                                .order_by('total DESC').all()

            results = Pagination(page, NUM_PER_PAGE, results, request, 'get_food')

            temp = []

            for res in results.items:
                associations = Food_chemical.query.filter_by(
                    pubchem_id=res.pubchem_id, food_id=food_id)
                temp.append({'chemical': Chemical.query.filter_by(pubchem_id=res.pubchem_id).first(),
                            'associations': associations.first()})

            results.items = temp

            
        else:
            abort(404)

        return render_template('food/food_page.html',
                               subcategory=subcategory,
                               subcategory_that_exist=subcategory_that_exist,
                               food=food,
                               results=results.items,
                               next_url=results.next_url,
                               last_url=results.last_url,
                               prev_url=results.prev_url,
                               first_url=results.first_url,
                               has_next=results.has_next,
                               has_prev=results.has_prev,
                               page_number=results.page,
                               total_pages=results.pages)
    else:
        abort(404)



@app.route('/dietrx/get_disease', methods=['GET'])
def get_disease():
    if not request.args.get('disease_id'):
        return redirect(url_for('index'))

    disease_id = request.args.get('disease_id')
    disease = Disease.query.filter_by(disease_id=disease_id).first()
    
    page = request.args.get('page', 1, type=int)


    if(disease is not None):
        subcategory_that_exist = []
        if(len(disease.food_disease) != 0):
            subcategory_that_exist.append('food')
        if(len(disease.disease_gene) != 0):
            subcategory_that_exist.append('gene')
        if(len(disease.chemical_disease) != 0):
            subcategory_that_exist.append('chemical')
        subcategory = request.args.get('subcategory', subcategory_that_exist[0])

        if(subcategory == 'food'):
            
            results = db.session.query(Food_disease.food_id, 
                        db.func.count(Food_disease.food_id).label('total'))\
                        .filter_by(disease_id=disease_id).group_by(Food_disease.food_id)\
                        .order_by('total DESC').all()
            
            results = Pagination(page, NUM_PER_PAGE, results, request, 'get_disease')

            temp = []

            for res in results.items:
                temp.append({'food': Food.query.filter_by(food_id=res.food_id).first(),
                            'positive_associations': Food_disease.query.filter_by(food_id=res.food_id, disease_id=disease_id, association='positive').all(),
                            'negative_associations': Food_disease.query.filter_by(food_id=res.food_id, disease_id=disease_id, association='negative').all()})

            results.items = temp

        elif(subcategory == 'gene'):

            results = db.session.query(Disease_gene.gene_id)\
                        .filter_by(disease_id=disease_id).all()

            results = Pagination(page, NUM_PER_PAGE, results, request, 'get_disease')
            temp = []

            for res in results.items:
                associations = Disease_gene.query.filter_by(gene_id = res.gene_id, disease_id=disease_id)
                temp.append({'gene': Gene.query.filter_by(gene_id = res.gene_id).first(), 
                            'associations': associations.first()})

            results.items = temp

        elif(subcategory == 'chemical'):

            infered_results = db.session.query(Food_chemical.pubchem_id, db.func.count(Food_chemical.food_id).label('total'))\
                                .filter(Food_disease.disease_id == disease_id)\
                                .join(Food).join(Food_disease)\
                                .group_by(Food_chemical.pubchem_id).all()

            curated_results = db.session.query(Chemical_disease)\
                            .filter_by(disease_id=disease_id).join(Chemical).all()

            temp = {}
            for res in infered_results:
                temp[res.pubchem_id] = {'pubchem_id': res.pubchem_id,
                                        'infered_food': res.total,
                                        'association': 'Infered via foods',
                                        'reference': '-',
                                        'type': 'Infered'}

            for res in curated_results:
                if res.pubchem_id in temp:
                    temp[res.pubchem_id]['association'] = res.association
                    temp[res.pubchem_id]['reference'] = res.reference
                    temp[res.pubchem_id]['type'] = 'Infered/Curated'
                else:
                    temp[res.pubchem_id] = {'pubchem_id': res.pubchem_id,
                                            'infered_food': 0,
                                            'association': res.association,
                                            'reference': res.reference,
                                            'type': 'Curated'}
            
            results = sorted(list(temp.values()), key=lambda k: k['infered_food'], reverse=True)

            results = Pagination(page, NUM_PER_PAGE, results, request, 'get_disease')
            
            temp = []
            for res in results.items:
                q = db.session.query()
                temp.append({'chemical': Chemical.query.filter_by(pubchem_id=res['pubchem_id']).first(),
                            'pubchem_id': res['pubchem_id'],
                            'infered_food': res['infered_food'],
                            'association': res['association'],
                            'reference': res['reference'],
                            'type': res['type']})

            results.items = temp

            
        else:
            abort(404)
        
        
        return render_template('disease/disease_page.html',
                               subcategory=subcategory,
                               subcategory_that_exist=subcategory_that_exist,
                               disease=disease,
                               results=results.items,
                               next_url=results.next_url,
                               last_url=results.last_url,
                               prev_url=results.prev_url,
                               first_url=results.first_url,
                               has_next=results.has_next,
                               has_prev=results.has_prev,
                               page_number=results.page,
                               total_pages=results.pages)
    else:
        abort(404)


@app.route('/dietrx/get_chemical', methods=['GET'])
def get_chemical():
    if not request.args.get('pubchem_id'):
        return redirect(url_for('index'))

    pubchem_id = request.args.get('pubchem_id')
    chemical = Chemical.query.filter_by(pubchem_id=pubchem_id).first()

    page = request.args.get('page', 1, type=int)

    if (chemical is not None):

        subcategory_that_exist = []
        if(len(chemical.chemical_disease) != 0):
            subcategory_that_exist.append('disease')
        if(len(chemical.food_chemical) != 0):
            subcategory_that_exist.append('food')
        subcategory = request.args.get('subcategory', subcategory_that_exist[0])

        if(subcategory == 'food'):

            results = db.session.query(Food_chemical.food_id,
                              db.func.count(Food_chemical.food_id).label('total'))\
                            .filter_by(pubchem_id=pubchem_id).group_by(Food_chemical.food_id)\
                                                .order_by('total DESC').all()

            results = Pagination(page, NUM_PER_PAGE, results, request, 'get_chemical')

            temp = []

            for res in results.items:
                associations = Food_chemical.query.filter_by(
                    food_id=res.food_id, pubchem_id=pubchem_id)
                temp.append({'food': Food.query.filter_by(food_id=res.food_id).first(),
                            'associations': associations.first()})

            results.items = temp

        elif(subcategory == 'disease'):

            results = db.session.query(Chemical_disease.disease_id,
                              db.func.count(Chemical_disease.disease_id).label('total'))\
                            .filter_by(pubchem_id=pubchem_id).group_by(Chemical_disease.disease_id)\
                                            .order_by('total DESC').all()

            results = Pagination(page, NUM_PER_PAGE, results, request, 'get_chemical')
            temp = []

            for res in results.items:
                associations = Chemical_disease.query.filter_by(
                    disease_id=res.disease_id, pubchem_id=pubchem_id)
                temp.append({'disease': Disease.query.filter_by(disease_id=res.disease_id).first(),
                            'associations': associations.first()})

            results.items = temp

        else:
            abort(404)
        return render_template('chemical/chemical_page.html',
                               subcategory=subcategory,
                               subcategory_that_exist=subcategory_that_exist,
                               chemical=chemical,
                               results=results.items,
                               next_url=results.next_url,
                               last_url=results.last_url,
                               prev_url=results.prev_url,
                               first_url=results.first_url,
                               has_next=results.has_next,
                               has_prev=results.has_prev,
                               page_number=results.page,
                               total_pages=results.pages)
    else:
        abort(404)





@app.route('/dietrx/get_gene', methods=['GET'])
def get_gene():
    if not request.args.get('gene_id'):
        return redirect(url_for('index'))

    gene_id = request.args.get('gene_id')
    gene = Gene.query.filter_by(gene_id=gene_id).first()
    
    page = request.args.get('page', 1, type=int)


    if (gene is not None):

        subcategory_that_exist = []
        if(len(gene.food_gene) != 0):
            subcategory_that_exist.append('food')
        if(len(gene.disease_gene) != 0):
            subcategory_that_exist.append('disease')
        subcategory = request.args.get('subcategory', subcategory_that_exist[0])
        print(subcategory_that_exist)
        if(subcategory == 'food'):

            results = Food_gene.query.filter_by(gene_id=gene_id).all()

            temp = []
            for res in results:
                temp.append({'association': res,
                            'count': len(res.inference_network.split('|'))})

            results = sorted(temp, key=lambda x: x['count'], reverse=True)
            results = Pagination(page, NUM_PER_PAGE, results, request, 'get_gene')

            temp = []

            for res in results.items:
                association = res['association']
                ids = association.inference_network.split('|')
                diseases = Disease.query.filter(Disease.disease_id.in_(ids)).all()
                temp.append({'food': association.food,
                            'associations': association,
                            'diseases': diseases,
                            'num_of_diseases': res['count']})

            results.items = temp

        elif(subcategory == 'disease'):

            results = db.session.query(Disease_gene.disease_id, 
                        db.func.count(Disease_gene.disease_id).label('total'))\
                        .filter_by(gene_id=gene_id).group_by(Disease_gene.disease_id)\
                        .order_by('total DESC').all()
            

            results = Pagination(page, NUM_PER_PAGE, results, request, 'get_gene')
            temp = []

            for res in results.items:
                associations = Disease_gene.query.filter_by(disease_id = res.disease_id, gene_id=gene_id)
                temp.append({'disease': Disease.query.filter_by(disease_id = res.disease_id).first(), 
                            'associations': associations.first()})
            results.items = temp
        else:
            abort(404)
        return render_template('gene/gene_page.html',
                               subcategory=subcategory,
                               subcategory_that_exist = subcategory_that_exist,
                               gene=gene,
                               results=results.items,
                               next_url=results.next_url,
                               last_url=results.last_url,
                               prev_url=results.prev_url,
                               first_url=results.first_url,
                               has_next=results.has_next,
                               has_prev=results.has_prev,
                               page_number=results.page,
                               total_pages=results.pages)
    else:
        abort(404)
