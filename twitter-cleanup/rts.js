var rts = document.getElementsByClassName("tweet-context with-icn");

for (i = 0; i < rts.length; i++) {
	var children = rts[i].parentElement.parentElement.children[1].childElementCount;
	for (j = 0; j < children; j++) {
		var clase = rts[i].parentElement.parentElement.children[1].children[j].className;
		if (clase == "stream-item-footer") {
			rts[i].parentElement.parentElement.children[1].children[j].children[1].children[1].children[1].click();
		}
	}
}
