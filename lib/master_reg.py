
from tiedie_util import *
import operator
import math
import random
from scipy import stats
import numpy as np

class ActivityScores: 
	"""
		Uses the supplied pathway to find 

	"""

	def __init__(self, network, scores, min_hub=10, p=1):
		"""
			Input:
				network: net[source] = [(i, t)]
				scores: hash map of differential gene expression (think D-statistics from SAM)
				min_hub: minimum number of genes regulated transcriptionally required 
				to be considered as a potential 'master regulator'
				p: the power to raise each element to when computing the running sum
		"""

		# build a list of candidate regulators
		self.candidates = {}	

		for source in network:

			positive_regulon = set()
			negative_regulon = set()
			for (i, t) in network[source]:
				type, mode = classifyInteraction(i)	
				# only consider transcriptional regulation
				if mode != 't':
					continue

				if type == 1:
					positive_regulon.add(t)
				elif type == -1:
					negative_regulon.add(t)

			if (len(positive_regulon) + len(negative_regulon)) >= min_hub:
				self.candidates[source] = (positive_regulon, negative_regulon)

		self.generateRankings(scores)
		# for chisquare test
		self.generateCategories(scores)

	@staticmethod
	def getPval(real, background):

		count = 0.0
		empirical_pval = None
		if real >= 0:
			# sort in descending order
			for val in sorted(background, reverse=True):
				if val >= real:
					count += 1
				else:
					break
			empirical_pval = (count+1)/(len(background)+1)
		else:
			# ascending order	
			for val in sorted(background, reverse=False):
				if val <= real:
					count += 1
				else:
					break
			empirical_pval = (count+1)/(len(background)+1)

		return empirical_pval

		
	def scoreCandidatesFISHER(self):
	
		scores = {}	
		for c in self.candidates:
			pos, neg = self.candidates[c]
			pval = self.scoreCHISQ(pos, neg)
			scores[c] = pval

		return scores	

	def scoreCandidates(self, threshold=0.05, nperms=1000):
	
		scores = {}	
		for c in self.candidates:
			pos, neg = self.candidates[c]
			score = self.scoreReg(pos, neg)
			bg = self.generateBackground(c, nperms)
			pval = ActivityScores.getPval(score, bg)
			# filter first by p-value, then weight by the score
			if pval < threshold:
				scores[c] = (score, pval)

		return scores	

	def generateBackground(self, candidate, nperms):
	
		pos, neg = self.candidates[candidate]
		# sample of this set size
		# of random genes to generate each permutation
		background_scores = []
		for i in range(0, nperms):
			sampled_pos = set(random.sample(self.gene_list, len(pos)))
			sampled_neg = set(random.sample(self.gene_list, len(neg)))
			score = self.scoreReg(sampled_pos, sampled_neg)
			background_scores.append(score)	

		return background_scores	

	def generateCategories(self, scores):
		"""
		Used for fisher's exact test: bin positive and negative sets 
		of each
		"""

		# create two sets: genes are either significantly up or down in either
		self.pos_de_set = set()
		self.neg_de_set = set()

		for (gene, score) in sorted(scores.iteritems(), key=operator.itemgetter(1), reverse=True):
			if score > 0:
				self.pos_de_set.add(gene)
			else:
				self.neg_de_set.add(gene)
	

	def generateRankings(self, scores):

		"""
			scores: scores of differential gene expression. These canonically are 
			d-statistic values output from Significance of Microarrays (SAM, Tishirani 2003).
			Input as a hash-map.
			Store the results in the internal index
		"""

		# invert the list, and then merge the postive and negative lists
		# descending order

		# save this data	
		self.gene_list = []
		self.scores = scores

		forward_genes = []
		forward_scores = []
		for (gene, score) in sorted(scores.iteritems(), key=operator.itemgetter(1), reverse=True):
			self.gene_list.append(gene)
			forward_genes.append(gene)
			forward_scores.append(score)
		# ascending order
		reverse_genes = []
		reverse_scores = []
		for (gene, score) in sorted(scores.iteritems(), key=operator.itemgetter(1), reverse=False):
			reverse_genes.append(gene)
			reverse_scores.append(score)

		# maintain two indexes
		indexF = 0
		indexR = 0
		# index by (gene, class (positive or negative))
		R_c = []
		# scores are combined
		R_c_SCORES = []
		while True:

			# termination conditions
			if indexF >= len(forward_genes) and indexR >= len(reverse_genes):
				break
			# append from the other list if one is finished
			elif indexF >= len(forward_genes):
				# the gene name and set are indexed
				R_c.append( (reverse_genes[indexR], '-') )
				R_c_SCORES.append( -reverse_scores[indexR] )
				indexR += 1
				continue
			elif indexR >= len(reverse_genes):
				R_c.append( (forward_genes[indexF], '+') )
				R_c_SCORES.append( forward_scores[indexF] )
				indexF += 1
				continue
					
			f_score = forward_scores[indexF]
			# inverse score...
			r_score = -reverse_scores[indexR]

			if f_score > r_score:
				R_c.append( (forward_genes[indexF], '+') )
				R_c_SCORES.append( f_score )
				indexF += 1
			else:
				R_c.append( (reverse_genes[indexR], '-') )
				R_c_SCORES.append( r_score )
				indexR += 1

		self.scores = R_c_SCORES
		self.list = R_c	
		


	def scoreCHISQ(self, pos_query_set, neg_query_set):
		"""
		Use chisquare approximation to fisher's exact test
		to calculate p-values for each
		"""

		# compute probability of random distribution in each
		# category by simple combinatorics
		s1 = len(self.pos_de_set)
		s2 = len(self.neg_de_set)
		norm = float(s1+s2)
		s1 = s1/norm
		s2 = s2/norm
		# expected frequencies for each set
		expected = np.array([s1, s2])

		up_AGREE = float(len(pos_query_set.intersection(self.pos_de_set)))
		up_DISAGREE = float(len(pos_query_set.intersection(self.neg_de_set)))
		observed = np.array([up_AGREE, up_DISAGREE])
		UP_chisq, UP_pval = stats.chisquare(observed, expected)
		
		down_AGREE = float(len(neg_query_set.intersection(self.neg_de_set)))
		down_DISAGREE = float(len(neg_query_set.intersection(self.pos_de_set)))
		observed = np.array([down_DISAGREE, down_AGREE])
		DOWN_chisq, DOWN_pval = stats.chisquare(observed, expected)

		combined_p = UP_pval*DOWN_pval
		return combined_p	

	def scoreReg(self, pos_query_set, neg_query_set):
		"""
			
		"""

		# from Lim et al., 2009 PSB
		rs_const = float(2.0*len(self.scores)-(len(pos_query_set)+len(neg_query_set)))
		running_sum = 0.0

		# -- norm const
		sum_norm_const = 0.0
		for i in range(0, len(self.list)):
			gene, set = self.list[i]
			if (set == '-' and gene in neg_query_set) or (set == '+' and gene in pos_query_set):
				# compute the sum of abs values of all scores in this set to get a normalization 
				# constant at the end
				sum_norm_const += abs(self.scores[i])

		running_sum = 0.0
		max_rs = 0
		min_rs = 0
		for i in range(0, len(self.list)):

			gene, set = self.list[i]
			if (set == '-' and gene in neg_query_set) or (set == '+' and gene in pos_query_set):
				running_sum += self.scores[i]/sum_norm_const
			else:
				# score decreases in this case
				running_sum -= 1/rs_const	

			if running_sum > max_rs:
				max_rs = running_sum	
			elif running_sum < min_rs:
				min_rs = running_sum	

		return max_rs+min_rs


class SSActivityScores: 
	"""
	Sample-specific activity scores module. The approach is to compute a 'activity' score for each 
	hub and sample, by averaging the expression (vs normal) of it's regulon. A background distribution
	for each is then built from permuted data, and z-scores for each sample/hub pair are returned. 
	"""
	def __init__(self, network, expression_matrix, min_hub=10):


		NET_parents, NET_children = getTFparents(network)
		tf_candidates = set()
		for tf in children:
			if len(children[tf]) >= min_hub:
				tf_candidates.add(tf)
	
		# get expression activity scores
		self.sample_expr = getExpression(expression_matrix)
		self.sample_activities = getActivityScores(self.sample_expr, tf_candidates, NET_parents)
	
		# generate a background distribution based on permuted (real) data, 
		# then fit to a gaussian distribution 
		permuted_expr = permuteLabels(sample_expr, 30)	
		bg_act = getActivityScores(permuted_expr, tf_candidates, NET_parents)
		bg_stats, bg_activity = fitGeneData(bg_act)
	
		# z-scores based on fitted background data
		z_scores = getZScores(sample_act, bg_stats, len(tf_candidates))

	def fitGeneData(self, bg_activity_scores):
		"""
		Fit a normal distribution to the activity scores for each gene.
	
			Input
				activity_scores: permuted scores by sample
			Output
				summary: Hash indexed by gene, with mean/sd summary statistics
	
		"""
	
		activity = {}
		for sample in bg_activity_scores:
			for gene in bg_activity_scores[sample]:
				if gene not in activity:
					activity[gene] = []
				activity[gene].append(bg_activity_scores[sample][gene])
	
		distributions = {} 
		for gene in activity:
			distributions[gene] = Dist(activity[gene], method="gaussian")
			
		return (distributions, activity)

	def getActivityScores(expr_data, binary_threshold, tf_genes, tf_parents): 
	
		# the number of counts per gene, per sample 
		counts = {}
		# store the mean scores of each gene, for each sample
		activities = {}
	
		for sample in expr_data:
			activities[sample] = defaultdict(float)
			counts[sample] = defaultdict(int)
			for gene in expr_data[sample]:	
	
				val = expr_data[sample][gene]
	
				if abs(val) >= binary_threshold:
	
					if gene not in tf_parents:
						continue
	
					# check, is this downstream of a TF of interest? 
					# if so, add the TF, not the gene
					parents, activation_type = tf_parents[gene]
					for parent in tf_genes.intersection(parents):
					
						act = activation_type[parent]	
						tf_act = None
						# is this TF active? 
						if act == 'a':
							tf_act = val
						elif act == 'i':	
							tf_act = -1*val
	
						# add the activity, and the count
						activities[sample][parent] += tf_act
						counts[sample][parent] += 1
	
		# convert sums to means
		for sample in activities:
			for gene in activities[sample]:
				activities[sample][gene] = activities[sample][gene]/float(counts[sample][gene])
	
		return activities
	
	def getZScores(scores, stats_summary, num_tests):
		"""
		Return z-scores for activity against the supplied background
		distribution (summary statistics)	
		Input
			scores: a hash indexed by genes, values are activity scores
			stats_summary: summary statistics of the per gene distributions
		
		Returns:
			activity_z_scores: z-scores for each gene
		"""
		
		activity_z_scores = {}
	
		for sample in scores:
			activity_z_scores[sample] = {}
			for gene in scores[sample]:
	
				val = scores[sample][gene]
				
				p = stats_summary[gene].getP(val)
				z = stats_summary[gene].getZ(val)
				# correct by number of tests: i.e. the number of genes
				corrected_p = num_tests*p
	
				activity_z_scores[sample][gene] = (z, p, corrected_p)
	
		return activity_z_scores
	
	def permuteLabels(expr_data, num_permuted_samples, by_gene=False):
	
		data_by_gene = {}
		all_data = []
		for sample in expr_data:
			for gene in expr_data[sample]:
				if gene not in data_by_gene:
					data_by_gene[gene] = []
				data_by_gene[gene].append(expr_data[sample][gene])
				all_data.append(expr_data[sample][gene])
	
		permuted = {}
		for i in range(0, num_permuted_samples):
			permuted[i] = {}
			for gene in data_by_gene:
				vals = None
				if not by_gene:
					permuted[i][gene] = random.sample(all_data,1)[0]
				else:
					vals = data_by_gene[gene]
					# sample with replacement from that gene's data
					permuted[i][gene] = random.sample(vals,1)[0]
	
		return permuted
		