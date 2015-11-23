import web
from web import form
from httplib import IncompleteRead
import re,csv,nltk,textblob,json,cStringIO,time, datetime,sets,operator
import pandas as pd
import matplotlib.pyplot as plt
import pygal
from concurrent import futures
from random import choice
import tweepy 
from tweepy import Stream
from tweepy.streaming import StreamListener
from tweepy import OAuthHandler
import StringIO
import pygame
from pytagcloud import create_tag_image, make_tags, LAYOUT_MIX
from pytagcloud.lang.counter import get_tag_counts
#******************************************************RENDER TEMPLATE************************************************************************
render = web.template.render('templates/')
urls = (
    '/(.*)', 'index'
)
page = ''
fp = open('templates/page.txt')
while True:
	line = fp.readline()
	if not line:
		break
	page += line

#******************************************************GLOBAL VARIABLES***********************************************************************
res = {}
positiveTweets = {}
negativeTweets = {}
neutralTweets = {}
positiveTweets['tweet'] = []
negativeTweets['tweet'] = []
neutralTweets['tweet'] = []
positiveTweets['polarity'] = []
negativeTweets['polarity'] = []
neutralTweets['polarity'] = []
zipP = {}
zipN = {}
zipNu = {}	
stopWords = []
big_regex = ''
stemmer = nltk.LancasterStemmer()
#render pie chart
bio = cStringIO.StringIO()
pio = StringIO.StringIO()
#adwords
adwords = ['buy','buying','free','download','games','%','$']
tweets_data_path = 'namo.txt'

#*******************************************************REMOVE STOP WORDS*********************************************************************
def getStopWordList(stopWordListFileName):
		stopWords.append('at_user')
		stopWords.append('url')
		stopWords.append('rt')
		fp = open(stopWordListFileName)
		line = fp.readline()
		while line:
			word = line.strip()
			stopWords.append(word)
			line = fp.readline()
		fp.close()
		return stopWords
def removeStopWords( tweet ):
		for word in stopWords:
			tweet.strip(word)
		print 'Tweet after rem stopwords: ',tweet
		return tweet
#****************************************************TWITTER APP KEYS AND OAUTH***************************************************************
consumer_key = 'uz7AN0bO2Pn22y4kDKFIlQbRl'
consumer_secret = 'LrrnbtJ9G4giRUh1qNF0v8g8eeXGyj7D4ieuyjJ5BZovh2k3Zd' 
access_token = '3194634037-nmTac6OSrnAZDoRbqh1upHMWRozKe3uIR9TMEl7'
access_secret = '6n6P6gciGtgDBlZ9LLIpCxMaUiEP9sGlqHv1DCC6SblGw'
auth = OAuthHandler(consumer_key, consumer_secret)
auth.set_access_token(access_token, access_secret)
#****************************************************TWITTER STREAMING************************************************************************
def stream_tweets( tags ):
	class TweetListener(StreamListener):
	    def __init__(self, limit):
			self.start = 0		
			self.total = limit
	    def on_data(self, data):
			saveFile = open(tweets_data_path,'a')
			if self.start <= self.total :
				data_json = json.loads( data )
				#remove retweets and tweets with adwords
				try:				
					if not data_json['text'].lower().startswith('rt') and not any( word in data_json['text'].lower() for word in adwords ):
						saveFile.write( data )
						saveFile.write('\n')
						print 'Count: ',self.start
						self.start += 1
				except KeyError,IncompleteRead:
					pass
				
			else:
				print 'Done streaming!'
				saveFile.close()
				return False
			return True
	    def on_error(self, status):
		print status
	print 'tags:: ',tags
	stream = Stream(auth, TweetListener(100) )
	stream.filter(languages=["en"],track=tags)
#***********************************************RENDERING INDEX TEMPLATE**********************************************************************
class index:
    def POST(self,name):
		data = web.input()
	     	tags = data.tags
		tags1 = [ tag for tag in tags.split(', ') ]
		print 'Tags: ',tags
		#give tags as filters to twitter_streaming.py
		#stream_tweets( tags )	
		stopWords = getStopWordList('stopwords.txt')
		print 'finished streaming!!'
		#run analysis.py on the tweets
		run_pgm( page )
		#print 'page: ',page		
		return print_tweets( page,tags )
		
    def GET(self,name):
	      	return page

if __name__ == "__main__":
    app = web.application(urls, globals())
    app.run()
#******************************************************BEGIN EXECUTION************************************************************************
def run_pgm( page ):
	start_time = time.time()
	global zipP,zipN,zipNu,res
	page += '''
<h3 class="hiddenmsg title col-md-12 col-xs-12">hold on...we're mining tweets...</h3>'''.encode("utf-8")
#*****************************************************PROCESSING TWEETS***********************************************************************
	def process_tweet(tweet):
		#print 'tweet before processing:',tweet,'after'
		#convert to lower case	
		tweet = tweet.lower()
		tweet = replaceTwoOrMore(tweet)
		#convert www.* or http:* to url
		tweet = re.sub('((www\.[^\s]+)|((http|https)://[^\s]+))','url',tweet)
		#covert @username to at_user
		tweet = re.sub('@[^\s]+','at_user',tweet)
		#remove additional whitespaces
		tweet = re.sub('[\s]+',' ',tweet)
		tweet = re.sub('[\']','',tweet)
		#replace #word with word
		tweet = re.sub(r'#([^\s]+)',r'\1',tweet)
		#trim
		tweet = tweet.strip("'");
		tweet = tweet.strip()
		tweet = removeStopWords( tweet )
		return tweet
	def replaceTwoOrMore(s):
		#look for 2/more reps of the charc and replace with the charc itself
		pattern = re.compile(r"(.)\1{1,}",re.DOTALL) # re.DOTALL makes '.' match anything INCL newline
		return pattern.sub(r"\1\1",s)
	#split tweet and get individual words which are not in the stopwords list
	def getFeatureVector(tweet):
		featureVector = []
		#split tweet into words
		words = tweet.split()
		for w in words:
			#replace 2/more
			w = replaceTwoOrMore(w)
			w = w.strip('\'"?,')
			w= re.sub('[.,]$','',w)
			#stemming
			if ( w.endswith('ing') or w.endswith('ed') or w.endswith('ses') ):
				w = stemmer.stem(w) 
			#check if word starts with alphabet or emoticon
			val = re.search(r"(^[a-zA-Z][a-zA-Z0-9]*$)|([:();@])",w)
			#ignore if it's a stop word
			if ( w in stopWords or val is None):
				continue
			else:
				featureVector.append(w.lower())
				#print featureVector
	 	return featureVector
#*************************************************EXTRACTING FEATURE VECTORS******************************************************************
	#return dictionary of words with true/false
	def extract_features( tweet ):
		tweet_words = tweet
		#print 'tweet words: ',tweet_words
		features = {}
		#print 'in extr feaures, featureList: ',featureList
		for word in featureList:
			features['contains(%s)' % word] =  (word in tweet_words) 
		return features

	def get_words_in_tweets(tweets):
		    all_words = []
		    for (words, sentiment) in tweets:
		      all_words.extend(words)
		    return all_words

	def get_word_features(wordlist):
		   # print 'wordlist: ',wordlist
		    wordlist = nltk.FreqDist(wordlist)
		    #print 'wordlist: '
		    
		    word_features = wordlist.keys()
		    return word_features
#*****************************************************TRAINING NAIVE BAYES CLASSIFIER*********************************************************
	#read tweets from training_set.txt
	#read featureList from featureList.txt
	tweets = []
	featureList = []
	tweets = json.load(open("training_set.txt","rb"))
	featureList = json.load(open("featureList.txt","rb"))

	#from file training/countValues.txt
	fp = open('MODULES/training/countValues.txt','rb')
	positive_review_count = int( fp.readline() )
	negative_review_count = int( fp.readline() )
	prob_positive = float( fp.readline() )
	prob_negative = float( fp.readline() )

	#get freqDist of words
	positive_counts = {}
	negative_counts = {}
	#from file training/negCounts.json
	json1_file = open('MODULES/training/negCounts.json')
	str_data = json1_file.read()
	negative_counts = json.loads(str_data)
	#from file training/posCounts.json
	json1_file = open('MODULES/training/posCounts.json')
	str_data = json1_file.read()
	positive_counts = json.loads(str_data)

	def make_class_prediction(text, counts, class_prob, class_count):
	  #class_prob => prior probablity
	  #counts => no of times a particular word appears in the main freqDist
	  prediction = 1
	  text_counts = Counter(re.split("\s+", text))
	  #print 'Text Counts: ', text_counts
	  for word in text_counts:
	      # For every word in the text, we get the number of times that word occured in the reviews for a given class, add 1 to smooth 		the value, and divide by the total number of words in the class (plus the class_count to also smooth the denominator).
	      # Smoothing ensures that we don't multiply the prediction by 0 if the word didn't exist in the training data.
	      # We also smooth the denominator counts to keep things even.
	      value = text_counts.get(word) * ((counts.get(word, 0) + 1) / (sum(counts.values()) + class_count))
	      prediction *=  value
	      # Now we multiply by the probability of the class existing in the documents.
	  
	training_set = nltk.classify.util.apply_features(extract_features, tweets)
	# Train the classifier
	NBClassifier = nltk.NaiveBayesClassifier.train(training_set)
	print NBClassifier.show_most_informative_features(30)
#******************************************************DYNAMIC EXECUTION BEGINS***************************************************************
	polarity = 0.0
	tweets_data = []
	tweets_file = open(tweets_data_path, "r")
	for line in tweets_file:
	    try:
		tweet = json.loads(line)
		#tweets_data.append(tweet)
		tweet = process_tweet( tweet['text'] )
		tweetblob = textblob.TextBlob( tweet )
		polarity = tweetblob.sentiment.polarity
		# neg_pred = make_class_prediction(tweet, negative_counts, prob_negative, negative_review_count)
		# pos_pred = make_class_prediction(tweet, positive_counts, prob_positive, positive_review_count)
		#print 'tweet: ',tweet	
		result = NBClassifier.classify(extract_features(tweet))
		print 'Tweet: ',tweet,' POLARITY: ',polarity,' RESULT: ',result
		if result == 'positive' or polarity >= 0.1:
			positiveTweets['tweet'].append( tweet )
			positiveTweets['tweet'] = list(set(positiveTweets['tweet']))
			positiveTweets['polarity'].append( (polarity+0.1) ) 
			c1 = len(positiveTweets['tweet'])
		elif result == 'negative'or polarity<= -0.1:
			negativeTweets['tweet'].append( tweet )
			negativeTweets['polarity'].append( (polarity-0.1) )
			negativeTweets['tweet'] = list(set(negativeTweets['tweet'])) 
			c2 = len(negativeTweets['tweet'])
		else: 
			neutralTweets['tweet'].append( tweet )
			neutralTweets['polarity'].append( (polarity) )
			neutralTweets['tweet'] = list(set(neutralTweets['tweet'])) 
			c3 = len(neutralTweets['tweet'])
	    except:
		continue
	print 'Out of this LOOOOOOOOOOP!'
	#raw_input()
	#saving results in res
	res['positive'] = [c1]
	res['negative'] = [c2]
	res['neutral'] = [c3]
	#sort the tweet lists by decreasing polarity
	zipP = zip( positiveTweets['tweet'],positiveTweets['polarity'])
	zipN = zip( negativeTweets['tweet'],negativeTweets['polarity'])
	zipNu = zip( neutralTweets['tweet'],neutralTweets['polarity'])

	zipP = sorted(zipP, key=operator.itemgetter(1), reverse = True)
	zipN = sorted(zipN, key=operator.itemgetter(1), reverse = True)
	zipNu = sorted(zipNu, key=operator.itemgetter(1), reverse = True)

	#Pie Chart		
	df = pd.DataFrame( res, columns=['positive','negative','neutral'])
	fig,ax = plt.subplots()
	plt.pie(res.values(),labels=['positive','neutral','negative'],colors=['aqua','grey','crimson'],autopct="%1.1f%%")
	plt.title('Sentiment analysis')
	plt.axis('equal')
	plt.savefig(bio, format = "png")
	#Tag Cloud
	
	pos_text = ''
	neg_text = ''
	neu_text = ''
	print 'Only 100 tweets!',positiveTweets['tweet'][:100]
	
	for word in positiveTweets['tweet'][:10]:
		pos_text+=word+' '
	for word in negativeTweets['tweet'][:10]:
		neg_text+=word+' '
	for word in neutralTweets['tweet'][:10]:
		neu_text+=word+' '
	ptags = make_tags(get_tag_counts(pos_text), maxsize=150)
	ntags = make_tags(get_tag_counts(neg_text), maxsize=150)
	nutags = make_tags(get_tag_counts(neu_text), maxsize=150)
	print 'ptags',len(ptags)
	create_tag_image(ptags, 'static/pcloud.png', size=(900, 600), layout=LAYOUT_MIX, fontname='Molengo', rectangular=True)
	print 'created pcloud'
	raw_input()	
	create_tag_image(ntags, 'static/negcloud.png', size=(900, 600), layout=LAYOUT_MIX, fontname='Molengo', rectangular=True)	
	print 'created pcloud'
	raw_input()	
	create_tag_image(nutags, 'static/nucloud.png', size=(900, 600), layout=LAYOUT_MIX, fontname='Molengo', rectangular=True)
	print 'created pcloud'
	raw_input()	
		
	#print total time to execute
	print("--- %s seconds ---" % (time.time() - start_time))

#***************************************************RENDER WEBPAGE****************************************************************************
def print_tweets( page,tags ):
	global zipP,zipN,zipNu
	page = re.sub('hiddenmsg','hiddenmsg hide',page)	
	line = '''<h3 class="title col-md-12 col-xs-12">check out the top tweets on '''+tags+''' here!</h3>
	<div class="col-md-4">
	<div class="positiveBox box clearfix">
	<h4 class="col-md-12 col-xs-12 smalltitle">positive</h4>
	<ul class="col-md-12 col-xs-12">'''
	for tweet,pol in zipP:
		tweet = re.sub('(at_user)|(url)','',tweet).strip()
		line += '''<li>'''+ tweet + '''<br/><b>POLARITY:'''+str(pol).encode('utf-8')+'''</b></li>'''
	line += '''</ul></div></div>'''
	page += line.encode("utf-8")
	line = '''<div class="col-md-4">
	<div class="negativeBox box clearfix">
	<h4 class="col-md-12 col-xs-12 smalltitle">negative</h4>
	<ul class="col-md-12 col-xs-12">'''
	for tweet,pol in zipN:
		tweet = re.sub('(at_user)|(url)','',tweet).strip()		
		line += '''<li>'''+ tweet + '''<br/><b>POLARITY:'''+str(pol).encode('utf-8')+'''</b></li>'''
	line += '''</ul></div></div>'''
	page += line.encode("utf-8")
	line = '''<div class="col-md-4">
	<div class="neutralBox box clearfix">
	<h4 class="col-md-12 col-xs-12 smalltitle">neutral</h4>
	<ul class="col-md-12 col-xs-12">'''
	for tweet,pol in zipNu:
		tweet = re.sub('(at_user)|(url)','',tweet).strip()
		line += '''<li>'''+ tweet + '''<br/><b>POLARITY:'''+str(pol).encode('utf-8')+'''</b></li>'''
	line += '''</ul></div></div>'''
	line += '''<h4 class="smalltitle col-md-12 col-xs-12">visualize your data</h4>'''
	line += '''<div class="col-md-4 col-xs-12"><h3 class="text-center">POSITIVE TAG CLOUD</h3><br/><img src="./static/pcloud.png"/></div>'''
	line += '''<div class="col-md-4 col-xs-12"><h3 class="text-center">NEGATIVE TAG CLOUD</h3><br/><img src="./static/negcloud.png"/></div>'''
	line += '''<div class="col-md-4 col-xs-12"><h3 class="text-center">NEUTRAL TAG CLOUD</h3><br/><img src="./static/nucloud.png"/></div>'''
	line += '''<div class="col-md-6 col-md-push-3 col-xs-12"><img src="data:image/png;base64,%s"/></div>''' % bio.getvalue().encode("base64").strip()
	#last 3 closing div
	line += '''</div></div></div>'''
	page += line.encode("utf-8")
	return page

