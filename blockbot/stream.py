'''
    stream
    ======

    Base handler around Twitter's filtered streams API.

    For documentation reference, see:
        https://developer.twitter.com/en/docs/twitter-api/v1/tweets/filter-realtime/guides/basic-stream-parameters
'''

import tweepy

from . import api


#import tweepy
##override tweepy.StreamListener to add logic to on_status
#class MyStreamListener(tweepy.StreamListener):
#
#    def on_status(self, status):
#        print(status.text)
#
#    def on_error(self, status_code):
#        if status_code == 420:
#            #returning False in on_error disconnects the stream
#            return False
#
#        # returning non-False reconnects the stream, with backoff.


#myStreamListener = MyStreamListener()
#myStream = tweepy.Stream(auth = api.auth, listener=myStreamListener)

#myStream.filter(track=['python'])
#myStream.filter(follow=["2211149702"])
#myStream.filter(track=['python'], is_async=True)
