var tweets = document.getElementsByClassName("js-actionDelete");

for (i = 0; i < tweets.length; i++) {
	tweets[i].click();
	document.getElementsByClassName("EdgeButton EdgeButton--danger delete-action")[0].click();
}
