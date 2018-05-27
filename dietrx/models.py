from dietrx import db
from dietrx.search import add_to_index, remove_from_index

class SearchableMixin(object):
    # @classmethod
    # def search(cls, expression, page, per_page):
    #     ids, total = query_index(cls.__tablename__, expression, page, per_page)
    #     if total == 0:
    #         return cls.query.filter_by(id=0), 0
    #     when = []
    #     for i in range(len(ids)):
    #         when.append((ids[i], i))
    #     return cls.query.filter(cls.id.in_(ids)).order_by(
    #         db.case(when, value=cls.id)), total

    # @classmethod
    # def before_commit(cls, session):
    #     session._changes = {
    #         'add': [obj for obj in session.new if isinstance(obj, cls)],
    #         'update': [obj for obj in session.dirty if isinstance(obj, cls)],
    #         'delete': [obj for obj in session.deleted if isinstance(obj, cls)]
    #     }

    # @classmethod
    # def after_commit(cls, session):
    #     id = ''
    #     if(cls.__tablename__ == 'food'):
    #         id = 'food_id'
    #     elif(cls.__tablename__ == 'disease'):
    #         id = 'disease_id'
    #     elif(cls.__tablename__ == 'gene'):
    #         id = 'gene_id'
    #     else:
    #         print('wrong table')
    #         return

    #     for obj in session._changes['add']:
    #         add_to_index(cls.__tablename__, obj, id)
    #     for obj in session._changes['update']:
    #         add_to_index(cls.__tablename__, obj, id)
    #     for obj in session._changes['delete']:
    #         remove_from_index(cls.__tablename__, obj, id)
    #     session._changes = None

    @classmethod
    def reindex(cls, id):
        for obj in cls.query:
            add_to_index(cls.__tablename__, obj, id)



class Food(SearchableMixin, db.Model):
    __searchable__ = ['display_name', 'common_names', 'scientific_name', 'food_category']
    __separators__ = {'common_names': '; '}
    food_id = db.Column(db.String(128), primary_key=True)
    display_name = db.Column(db.String(128))
    common_names = db.Column(db.Text)
    scientific_name = db.Column(db.Text)
    food_category = db.Column(db.String(128))
    tax_id = db.Column(db.Integer)
    genes = db.relationship("Gene", secondary="food_gene")
    diseases = db.relationship("Disease", secondary="food_disease")

    def __repr__(self):
        return '<Food {}>'.format(self.display_name)



class Disease(SearchableMixin, db.Model):
    __searchable__ = ['disease_name', 'disease_synonyms', 'disease_category']
    __separators__ = {'disease_synonyms': '|', 'disease_category': '|'}
    disease_id = db.Column(db.String(128), primary_key=True)
    disease_name = db.Column(db.Text)
    disease_synonyms = db.Column(db.Text)
    disease_category = db.Column(db.Text)
    genes = db.relationship("Gene", secondary="disease_gene")
    foods = db.relationship("Food", secondary="food_disease")

    def __repr__(self):
        return '<Disease {}>'.format(self.disease_name)


class Gene(SearchableMixin, db.Model):
    __searchable__ = ['gene_id']
    __separators__ = {}
    gene_id = db.Column(db.String(128), primary_key=True)
    diseases = db.relationship('Disease', secondary='disease_gene')
    foods = db.relationship('Food', secondary='food_gene')

    def __repr__(self):
        return '<Gene {}>'.format(self.gene_id)


class Chemical(db.Model):
    pubchem_id = db.Column(db.Integer, primary_key=True)
    common_name = db.Column(db.Text, nullable=True, index=True)
    database = db.Column(db.Text, nullable=True, index=True)
    reference = db.Column(db.Text, nullable=True, index=True)
    iupac_name = db.Column(db.Text, nullable=True, index=True)
    functional_group = db.Column(db.Text, nullable=True, index=True)
    functional_group_idx = db.Column(db.Text, nullable=True, index=True)
    bitter_taste = db.Column(db.Boolean, index=True)
    sweet_taste = db.Column(db.Boolean, index=True)
    tasteless_taste = db.Column(db.Boolean, index=True)
    predicted = db.Column(db.Boolean, index=True)
    taste = db.Column(db.Text, index=False)
    smiles = db.Column(db.Text, index=False)
    molecular_weight = db.Column(db.Float, index=False,
                                 nullable=True)
    num_hydrogen_atoms = db.Column(db.Integer, index=False, nullable=True)
    num_heavy_atoms = db.Column(db.Integer, index=False, nullable=True)
    num_rings = db.Column(db.Integer, index=False, nullable=True)
    num_rotatablebonds = db.Column(db.Integer, index=False, nullable=True)
    number_of_aromatic_bonds = db.Column(db.Integer, index=False,
                                         nullable=True)
    num_atoms = db.Column(db.Integer, index=False, nullable=True)
    hba_count = db.Column(db.Integer, index=False, nullable=True)
    hbd_count = db.Column(db.Integer, index=False, nullable=True)
    hyrophilic_index = db.Column(db.Float, index=False,
                                 nullable=True)
    alogp = db.Column(db.Float, index=False, nullable=True)

    def __repr__(self):
        return '<Molecule {}>'.format(self.mol_id)


class Food_disease(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    pmid = db.Column(db.Integer, db.ForeignKey('references.pmid'))
    reference = db.relationship('References', backref=db.backref('food_disease'))
    food_id = db.Column(db.String(128), db.ForeignKey('food.food_id'))
    disease_id = db.Column(db.String(128), db.ForeignKey('disease.disease_id'))
    association = db.Column(db.String(100))
    food = db.relationship("Food", backref=db.backref('food_disease'))
    disease = db.relationship("Disease", backref=db.backref('food_disease'))

    def __repr__(self):
        return '<Food Disease {}>'.format(self.id)


class Disease_gene(db.Model):
    gene_id = db.Column(db.String(128), db.ForeignKey('gene.gene_id'), primary_key=True)
    disease_id = db.Column(db.String(128), db.ForeignKey('disease.disease_id'), primary_key=True)
    reference = db.Column(db.String(100))
    disease = db.relationship("Disease", backref=db.backref('disease_gene'))
    gene = db.relationship("Gene", backref=db.backref('disease_gene'))

    def __repr__(self):
        return '<Disease Gene {}>'.format(self.gene_id)


class Food_gene(db.Model):
    food_id = db.Column(db.String(128), db.ForeignKey('food.food_id'), primary_key=True)
    gene_id = db.Column(db.String(128), db.ForeignKey('gene.gene_id'), primary_key=True)
    disease_categories = db.Column(db.Text)
    food = db.relationship("Food", backref=db.backref('food_gene'))
    gene = db.relationship("Gene", backref=db.backref('food_gene'))

    def __repr__(self):
        return '<Food Gene {}>'.format(self.food_id)


class References(db.Model):
    pmid = db.Column(db.Integer, primary_key=True)
    authors = db.Column(db.String(512))
    date = db.Column(db.String(128))
    journal_name = db.Column(db.String(512))
    journal_name_abbr = db.Column(db.String(512))
    publication_type = db.Column(db.String(512))
    title = db.Column(db.String(1024))

    def __repr__(self):
        return '<References {}>'.format(self.pmid)


class Chemical_disease(db.Model):
    pubchem_id = db.Column(db.String(128), db.ForeignKey('chemical.pubchem_id'), primary_key=True)
    disease_id = db.Column(db.String(128), db.ForeignKey('disease.disease_id'), primary_key=True)
    chemical = db.relationship("Chemical", backref=db.backref('chemical_disease'))
    disease = db.relationship("Disease", backref=db.backref('chemical_disease'))

    def __repr__(self):
        return '<Chemical Disease {}>'.format(self.pubchem_id)


class Food_chemical(db.Model):
    food_id = db.Column(db.String(128), db.ForeignKey(
        'food.food_id'), primary_key=True)
    pubchem_id = db.Column(db.String(128), db.ForeignKey(
        'chemical.pubchem_id'), primary_key=True)
    references = db.Column(db.Text)
    food = db.relationship("Food", backref=db.backref('food_chemical'))
    chemical = db.relationship(
        "Chemical", backref=db.backref('food_chemical'))

    def __repr__(self):
        return '<Food Chemical {}>'.format(self.food_id)
