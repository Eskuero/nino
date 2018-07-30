 
# Clean your Twitter!

You can use the following scripts **within the javascript console included in your web browser**. This code has been written to automatize the deletion of tweets and undo of retweets **from the default Twitter desktop webpage** (Tweetdeck is not supported).
Be careful when iterating the loop over too many posts because you may trigger Twitter into thinking you are abusing the service.
**It's all your own responsibility**.

## Deleting Tweets

The file tweets.js contains the code for doing this. For it to work properly **you have to do a search** using the following syntax:
`from:your_username to:mentioned_username since:yyyy-mm-dd until:yyyy-mm-dd keyword-ignore_keyword`

Per example if I wanted to list all of my tweets containing the word "linux" but not the word "windows" since the start of this year I would write:
`from:3skuero since:2018-01-01 linux -windows`

Once the search has completed you can check the results and scroll to load all the results if needed. If everything is fine running the script from the browser console will start deleting every tweet listed on the search.
Depending on the amount of tweets and the resources of your PC **it may even look like the browser froze**. Just be patient.

## Undoing RTs

Unlike for deleting **you can't query Twitter's database** to use keywords or timestamps, which means you will have to settle down for **scrolling as much as you can on your profile** to load all the content possible and then run the script.
