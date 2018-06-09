from dietrx import app
from flask import request, render_template, url_for, redirect, abort, Response, jsonify
from .models import *
import json
from .util import Pagination, autocomplete_search, search_elastic


NUM_PER_PAGE = 10



@app.route('/dietrx/', methods=['GET'])
@app.route('/dietrx/index', methods=['GET'])
def index():
    return render_template('search/search.html')



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
		print(subcategory_that_exist)

		if(subcategory == 'disease'):

			results = db.session.query(Food_disease.disease_id, 
							db.func.count(Food_disease.disease_id).label('total'))\
							.filter_by(food_id=food_id).group_by(Food_disease.disease_id)\
							.order_by('total DESC').all()

			results = Pagination(page, NUM_PER_PAGE, results, request, 'get_food')

			temp = []

			for res in results.items:
				associations = Food_disease.query.filter_by(disease_id = res.disease_id, food_id=food_id)
				q = db.session.query(Chemical)\
					.filter(Food_chemical.food_id == food_id)\
					.filter(Chemical_disease.disease_id == res.disease_id)\
					.filter(Food_chemical.pubchem_id == Chemical.pubchem_id, 
							Chemical_disease.pubchem_id == Chemical.pubchem_id)
				temp.append({'disease': Disease.query.filter_by(disease_id = res.disease_id).first(), 
							'positive_associations': associations.filter_by(association = 'positive').all(),
							'negative_associations': associations.filter_by(association = 'negative').all(),
							'inference_network': q.all()})


			results.items = temp
			
		elif(subcategory == 'gene'):

			results = db.session.query(Food_gene.gene_id, 
							db.func.count(Food_gene.gene_id).label('total'))\
							.filter_by(food_id=food_id).group_by(Food_gene.gene_id)\
							.order_by('total DESC').all()

			results = Pagination(page, NUM_PER_PAGE, results, request, 'get_food')

			temp = []

			for res in results.items:
				associations = Food_gene.query.filter_by(gene_id = res.gene_id, food_id=food_id)
				temp.append({'gene': Gene.query.filter_by(gene_id = res.gene_id).first(), 
							'associations': associations.first()})


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
				associations = Food_disease.query.filter_by(food_id = res.food_id, disease_id=disease_id)
				q = db.session.query(Chemical)\
                                    .filter(Food_chemical.food_id == disease_id)\
                                    .filter(Chemical_disease.disease_id == res.food_id)\
                                    .filter(Food_chemical.pubchem_id == Chemical.pubchem_id,
                                            Chemical_disease.pubchem_id == Chemical.pubchem_id)
				temp.append({'food': Food.query.filter_by(food_id = res.food_id).first(), 
							'positive_associations': associations.filter_by(association = 'positive').all(),
							'negative_associations': associations.filter_by(association = 'negative').all(),
							'inference_network': q.all()})

			
			results.items = temp

		elif(subcategory == 'gene'):

			results = db.session.query(Disease_gene.gene_id, 
						db.func.count(Disease_gene.gene_id).label('total'))\
						.filter_by(disease_id=disease_id).group_by(Disease_gene.gene_id)\
						.order_by('total DESC').all()
			

			results = Pagination(page, NUM_PER_PAGE, results, request, 'get_disease')
			temp = []

			for res in results.items:
				associations = Disease_gene.query.filter_by(gene_id = res.gene_id, disease_id=disease_id)
				temp.append({'gene': Gene.query.filter_by(gene_id = res.gene_id).first(), 
							'associations': associations.first()})

			results.items = temp

		elif(subcategory == 'chemical'):

			results = db.session.query(Chemical_disease.pubchem_id,
                              db.func.count(Chemical_disease.pubchem_id).label('total'))\
                            .filter_by(disease_id=disease_id).group_by(Chemical_disease.pubchem_id)\
                      						.order_by('total DESC').all()

			results = Pagination(page, NUM_PER_PAGE, results, request, 'get_disease')
			temp = []

			for res in results.items:
				associations = Chemical_disease.query.filter_by(
				    pubchem_id=res.pubchem_id, disease_id=disease_id)
				temp.append({'chemical': Chemical.query.filter_by(pubchem_id=res.pubchem_id).first(),
                            'associations': associations.first()})

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

		subcategory = request.args.get('subcategory', 'food')

		if(subcategory == 'food'):

			results = db.session.query(Food_gene.food_id, 
							db.func.count(Food_gene.food_id).label('total'))\
							.filter_by(gene_id=gene_id).group_by(Food_gene.food_id)\
							.order_by('total DESC').all()

			results = Pagination(page, NUM_PER_PAGE, results, request, 'get_gene')

			temp = []

			for res in results.items:
				associations = Food_gene.query.filter_by(food_id = res.food_id, gene_id=gene_id)
				temp.append({'food': Food.query.filter_by(food_id = res.food_id).first(), 
							'associations': associations.first()})


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
