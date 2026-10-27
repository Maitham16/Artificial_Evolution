extends Control
var model
var mode: String = "population"
var title: String = "POPULATION"
var activation := PackedFloat64Array()
var accent := Color("a8dbaf")

func _draw() -> void:
	var font=get_theme_default_font()
	draw_string(font,Vector2(14,24),title,HORIZONTAL_ALIGNMENT_LEFT,-1,13,Color("b9c9bc"))
	if model==null:return
	if mode=="lineages":_lineages(font);return
	if mode=="neurons":
		for i in range(8):
			var y=48+i*19;draw_string(font,Vector2(14,y+4),str(i+1),HORIZONTAL_ALIGNMENT_LEFT,-1,11,Color("9fb0a6"))
			draw_line(Vector2(37,y),Vector2(size.x-14,y),Color("304642"),5)
			var value=activation[i] if activation.size()==8 else 0.0
			var middle=(size.x+23)*.5
			draw_line(Vector2(middle,y),Vector2(middle+value*(size.x-60)*.5,y),accent if value>=0 else Color("dcbb84"),5)
		return
	var rows=model.history if mode=="fitness" else model.samples
	var rect=Rect2(15,41,maxf(10,size.x-30),maxf(10,size.y-64))
	for i in range(3):
		var y=rect.position.y+rect.size.y*i/2
		draw_line(Vector2(rect.position.x,y),Vector2(rect.end.x,y),Color("2c423d"),1)
	if rows.is_empty():
		draw_string(font,Vector2(16,75),"Complete a generation to see fitness.",HORIZONTAL_ALIGNMENT_LEFT,size.x-25,12,Color("83998e"));return
	var key="alive" if mode=="population" else "mean_meals" if mode=="meals" else "mean_fitness"
	var high=1.0;var low=0.0
	for row in rows:high=maxf(high,float(row[key]));low=minf(low,float(row[key]))
	var points=PackedVector2Array()
	var stride=maxi(1,rows.size()/220)
	for i in range(0,rows.size(),stride):
		points.append(Vector2(rect.position.x+float(i)/maxi(1,rows.size()-1)*rect.size.x,rect.end.y-(float(rows[i][key])-low)/(high-low)*rect.size.y))
	if points.size()>1:draw_polyline(points,accent,2.0,true)
	elif points.size()==1:draw_circle(points[0],2.5,accent)
	draw_string(font,Vector2(size.x-76,25),"%.1f" % rows[-1][key],HORIZONTAL_ALIGNMENT_RIGHT,60,17,accent)

func _lineages(font: Font) -> void:
	var rows={};var current={}
	for c in model.agents:current[c.root]=current.get(c.root,0)+1
	var roots=current.keys();roots.sort_custom(func(a,b):return current[a]>current[b])
	roots=roots.slice(0,mini(12,roots.size()))
	var first=maxi(1,model.generation-7)
	for c in model.archived:
		var g=int(str(c.id).get_slice(":",0).trim_prefix("g"))
		var key=str(c.root)+":"+str(g);rows[key]=rows.get(key,0)+1
	for c in model.agents:
		var key=str(c.root)+":"+str(model.generation);rows[key]=rows.get(key,0)+1
	var width=maxf(25,(size.x-170)/maxi(1,model.generation-first+1))
	for g in range(first,model.generation+1):
		draw_string(font,Vector2(145+(g-first)*width,65),"G%02d" % g,HORIZONTAL_ALIGNMENT_LEFT,-1,13,Color("b4c3b5"))
	var height=minf(38,(size.y-120)/maxi(1,roots.size()))
	for i in range(roots.size()):
		var root=roots[i];var y=100+i*height
		var color=Color.from_hsv(float(str(root).sha256_text().substr(0,6).hex_to_int())/16777215.0,.3,.88)
		draw_circle(Vector2(23,y-4),5,color)
		draw_string(font,Vector2(37,y),str(root),HORIZONTAL_ALIGNMENT_LEFT,100,13,color)
		var previous=Vector2.ZERO
		for g in range(first,model.generation+1):
			var count=int(rows.get(str(root)+":"+str(g),0))
			var point=Vector2(160+(g-first)*width,y-4)
			if count>0:
				if previous!=Vector2.ZERO:draw_line(previous,point,Color(color,.4),2,true)
				draw_circle(point,4+sqrt(count),Color(color,.8))
				draw_string(font,point+Vector2(14,4),str(count),HORIZONTAL_ALIGNMENT_LEFT,-1,11,color)
				previous=point
	draw_string(font,Vector2(15,size.y-18),"Largest 12 founder families · last 8 generations · full individual ancestry is exported",HORIZONTAL_ALIGNMENT_LEFT,size.x-25,12,Color("94ab9b"))
