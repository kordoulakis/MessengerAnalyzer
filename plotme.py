"""
@author: Elias Kordoulas
@purpose: This file contains all the functions to display the desired data
@using: pyplot for plotting, numpy for obvious reasons and seaborn for nice style
"""
import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np

# creates a color palette for the graph, one here is clearly defined
# and the other picks from random color array
# you can create your own or remove the if else entirely and rely on the random ones
#
# @length refers to the ammount of colors the function requests
# @bar is refers to if the function is plotting a bar. If yes then we prefer a gradient  
# @**kwargs
#   it's only used in case a function wants a more contrasty palette (contrast=True)
#   the name of the kw is never used to just take it as an optional bool
def getColors(length,bar,**kwargs):
    colors = list()
    if (len(kwargs) > 0) and length == 2:
        colors = ['#E74C3C', '#3498DB', '#F49D1E', '#2C3E50','#1C8200']
        return colors
    if (length <= 6):
        colors = ['#7b52ab','#c450a2','#f85a88','#ff7a65','#ffa843','#ffd933']
    elif (length<=20 and not bar ): #TODO change this, better colors
        tableau20 = [(31, 119, 180), (174, 199, 232), (255, 127, 14), (255, 187, 120),    
                (44, 160, 44), (152, 223, 138), (214, 39, 40), (255, 152, 150),    
                (148, 103, 189), (197, 176, 213), (140, 86, 75), (196, 156, 148),    
                (227, 119, 194), (247, 182, 210), (127, 127, 127), (199, 199, 199),    
                (188, 189, 34), (219, 219, 141), (23, 190, 207), (158, 218, 229)]    
        # Scale the RGB values to the [0, 1] range, which is the format matplotlib accepts.  
        for i in range(len(tableau20)):
            r, g, b = tableau20[i]
            tableau20[i] = (r / 255., g / 255., b / 255.)    
        import random
        for i in range(length):
            r = random.randint(0,len(tableau20)-1)
            if (tableau20[r] not in colors) :
                colors.append(tableau20[r])
                tableau20.remove(tableau20[r])
    else:#yeah this is for those times. gradients of 80 values
        colors=['#ffd60a', '#ffd100', '#ffcb00', '#ffc500',#orange to purple gradient
                '#ffbf00', '#ffb900', '#ffb300', '#ffac00',
                '#ffa60b', '#ff9f15', '#ff971d', '#ff9025',
                '#ff882c', '#ff8033', '#ff783a', '#ff6f41',
                '#ff6648', '#ff5c4e', '#ff5155', '#ff455c',
                '#ff3863', '#ff286b', '#ff0d72', '#ff007a',
                '#ff0081', '#ff0089', '#ff0091', '#ff009a',
                '#ff00a2', '#ff00aa', '#ff00b3', '#ff00bc',
                '#ff00c4', '#ff00d5', '#ff00de', '#ff00e7',
                '#f400ef', '#e700f7', '#da00ff', '#ED00FF',
                '#2cbdfe', '#2fb9fc', '#33b4fa', '#36b0f8',#blue to purple gradient
                '#3aacf6', '#3da8f4', '#41a3f2', '#449ff0',
                '#489bee', '#4b97ec', '#4f92ea', '#528ee8',
                '#568ae6', '#5986e4', '#5c81e2', '#607de0',
                '#6379de', '#6775dc', '#6a70da', '#6e6cd8',
                '#7168d7', '#7564d5', '#785fd3', '#7c5bd1',
                '#7f57cf', '#8353cd', '#864ecb', '#894ac9',
                '#8d46c7', '#9042c5', '#943dc3', '#9739c1',
                '#9b35bf', '#9e31bd', '#a22cbb', '#a528b9',
                '#a924b7', '#ac20b5', '#b01bb3', '#b317b1']
    return colors
### SPIDER GRAPH ###
#@plots a polar graph with specific ammount of edges
#@arguments this is a always a dict with {k : v}, no second dimensions (dict in dict) 
def plotSpiderGraph(this):
    from matplotlib.patches import Circle, RegularPolygon
    from matplotlib.path import Path
    from matplotlib.projections.polar import PolarAxes
    from matplotlib.projections import register_projection
    from matplotlib.spines import Spine
    from matplotlib.transforms import Affine2D
    def radar_factory(num_vars, frame='circle'):
        """Create a radar chart with `num_vars` axes.

        This function creates a RadarAxes projection and registers it.

        Parameters
        ----------
        num_vars : int
            Number of variables for radar chart.
        frame : {'circle' | 'polygon'}
            Shape of frame surrounding axes.

        """
        # calculate evenly-spaced axis angles
        theta = np.linspace(0, 2*np.pi, num_vars, endpoint=False)

        class RadarAxes(PolarAxes):

            name = 'radar'

            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                # rotate plot such that the first axis is at the top
                self.set_theta_zero_location('N')

            def fill(self, *args, closed=True, **kwargs):
                """Override fill so that line is closed by default"""
                return super().fill(closed=closed, *args, **kwargs)

            def plot(self, *args, **kwargs):
                """Override plot so that line is closed by default"""
                lines = super().plot(*args, **kwargs)
                for line in lines:
                    self._close_line(line)

            def _close_line(self, line):
                x, y = line.get_data()
                # FIXME: markers at x[0], y[0] get doubled-up
                if x[0] != x[-1]:
                    x = np.concatenate((x, [x[0]]))
                    y = np.concatenate((y, [y[0]]))
                    line.set_data(x, y)

            def set_varlabels(self, labels):
                self.set_thetagrids(np.degrees(theta), labels)

            def _gen_axes_patch(self):
                # The Axes patch must be centered at (0.5, 0.5) and of radius 0.5
                # in axes coordinates.
                if frame == 'circle':
                    return Circle((0.5, 0.5), 0.5)
                elif frame == 'polygon':
                    return RegularPolygon((0.5, 0.5), num_vars,
                                        radius=.5, edgecolor="k")
                else:
                    raise ValueError("unknown value for 'frame': %s" % frame)

            def draw(self, renderer):
                """ Draw. If frame is polygon, make gridlines polygon-shaped """
                if frame == 'polygon':
                    gridlines = self.yaxis.get_gridlines()
                    for gl in gridlines:
                        gl.get_path()._interpolation_steps = num_vars
                super().draw(renderer)


            def _gen_axes_spines(self):
                if frame == 'circle':
                    return super()._gen_axes_spines()
                elif frame == 'polygon':
                    # spine_type must be 'left'/'right'/'top'/'bottom'/'circle'.
                    spine = Spine(axes=self,
                                spine_type='circle',
                                path=Path.unit_regular_polygon(num_vars))
                    # unit_regular_polygon gives a polygon of radius 1 centered at
                    # (0, 0) but we want a polygon of radius 0.5 centered at (0.5,
                    # 0.5) in axes coordinates.
                    spine.set_transform(Affine2D().scale(.5).translate(.5, .5)
                                        + self.transAxes)


                    return {'polar': spine}
                else:
                    raise ValueError("unknown value for 'frame': %s" % frame)

        register_projection(RadarAxes)
        return theta

    data = list(this.keys())
    values = list(this.values())
    N = len(data)
    theta = radar_factory(N, frame='polygon')
    from random import randint
    colour = getColors(N, True)[randint(0,79)]

    plt.figure(figsize=(12,9))
    ax = plt.subplot(projection='radar')

    title = 'Messages per '
    title += 'Day of the Week' if N == 7 else 'Time of Day'

    ax.set_title(title,position=(0.5, 1.1), ha='center')
    ax.plot(theta, values)
    ax.fill(theta, values,color=colour,alpha=0.8)
    ax.set_varlabels(data)
    plt.tight_layout()

    plt.show()

### LINE PLOTTING ###
#@plots a line graph, used through the perDay functions
#@*args
#   only using str(args[0]) to configure the title, nothing else. If left without it then there is a default set
def plotLineGraph_MessagesPerDay(this,*args):
    plt.figure(figsize=(12, 9))
    plt.xlabel("Dates", fontsize=16)
    plt.ylabel("Messages")
    title = 'Messages Per Day' if len(args) == 0 else 'Messages Per Day\nKeywords: '+ str(args[0])
    plt.title(title)

    ax = plt.subplot(111)    
    ax.spines["top"].set_visible(False)    
    ax.spines["bottom"].set_visible(False)    
    ax.spines["right"].set_visible(False)    
    ax.spines["left"].set_visible(False) 
    
    dates = [ k for k in this]
    values = [ v for k, v in this.items()]
    plt.xticks(np.arange(0,len(dates), len(dates)/10))
    
    #from scipy.ndimage.filters import gaussian_filter
    #values = gaussian_filter(values,sigma=3) #Makes for a more pleasing image, loses a lot of precision 
    plt.fill_between(dates,0, values,alpha=0.2,color='#f85a88')
    plt.plot(dates,values,lw=1.5, color = 'xkcd:salmon')
    plt.tight_layout()
    plt.show()

#@plots a line graph, takes a dict, the participantsList from main and a bool
#@caution if separate=True then multiple graphs will be created with a single line
#@if separate=False then all the lines will be plotted in the same graph with different colors, it's nice
def plotLineGraph_MessagesPerDayPerParticipant(this, participants, separate):
    colors = getColors(len(participants), False,contrast=True)
    plt.figure(figsize=(12, 9))
    ax = plt.subplot(111)    
    ax.spines["top"].set_visible(False)    
    ax.spines["bottom"].set_visible(False)    
    ax.spines["right"].set_visible(False)    
    ax.spines["left"].set_visible(False) 

    plt.xlabel("Dates")
    plt.ylabel("Messages per participant")

    plt.title("Messages per Day per Participant")

    listOfLists = [ [] for p in participants] 
    listOfLists.append([])
    values = list(this.values())
    dates = this.keys()

    plt.xticks(np.arange(0, len(dates), len(dates)/10))
    
    for d in values: 
        for v in d:
            listOfLists[participants.index(v)].append(d[v])
    
    for p in participants:
        if (separate):
            plt.subplot(len(participants),1,participants.index(p)+1)
            plt.xticks(np.arange(0, len(dates), len(dates)//10))
        plt.plot(dates, listOfLists[participants.index(p)], label = p,lw=2, alpha=0.6, color=colors[participants.index(p)])
        plt.legend()

    plt.show()

#@plots a line graph from a dict where {k:v} is {month : messages}
#the purpose of its existence eludes me right now, oh well
def plotLineGraph_MessagesPerMonth(this):
    from random import randint
    colors = getColors(len(this), False)
    color = colors[randint(0,len(colors))]
    plt.figure(figsize=(12, 9))
    plt.xlabel('Months', fontsize=16)
    plt.ylabel('Messages')
    plt.title('Messages per Month')
    ax = plt.subplot(111)    
    ax.spines["top"].set_visible(False)    
    ax.spines["bottom"].set_visible(False)    
    ax.spines["right"].set_visible(False)    
    ax.spines["left"].set_visible(False) 

    dates = [ k for k in this ]
    values = [v for k,v in this.items() ]
    plt.xticks(range(len(this)+1),rotation=30)
    plt.plot(dates, values, lw=2.5, color=color)
    plt.fill_between(dates,0, values,alpha=0.2,color=color)

    plt.tight_layout()
    plt.show()

#@plots a line graph, y is a list of values so it can be plotted immediately
def plotLineGraph_TimeOfResponsePerMessage(y, **kwargs):
    plt.figure(figsize=(12, 9))
    label = 'Response Time in '
    label += 'Seconds' if len(kwargs) == 0 else kwargs['time']
    plt.xlabel("Messages", fontsize=16)
    plt.ylabel(label)
    plt.title("Response Time Between Messages")

    ax = plt.subplot(111)    
    ax.spines["top"].set_visible(False)    
    ax.spines["bottom"].set_visible(False)    
    ax.spines["right"].set_visible(False)    
    ax.spines["left"].set_visible(False) 
    
    x = np.arange(0,len(y))

    plt.xticks(np.arange(0, len(y), len(y)/10))

    plt.xticks(rotation=30)

    plt.fill_between(x,0, y,alpha=0.2,color='#f85a88')
    plt.plot(x,y,lw=1.5, color = 'xkcd:salmon')
    plt.tight_layout()
    plt.show()

### BAR PLOTTING ####
#@plots a bar graph. 
#@caution wether or not there is a bar named 'Total' is configured in the totalMessages function in main
def plotBarGraph_TotalMessages_PerParticipant(this):
    colors = getColors(len(this),True)
    plt.figure(figsize=(12, 9))
    ax = plt.subplot(111)    
    ax.spines["top"].set_visible(False)    
    ax.spines["bottom"].set_visible(False)    
    ax.spines["right"].set_visible(False)    
    ax.spines["left"].set_visible(False)    

    plt.xlabel("Participants")
    plt.ylabel("Messages Sent")

    plt.bar(range(len(this)), list(this.values()), color=colors)
    plt.xticks(range(len(this)), list(this.keys()), rotation=15)
    plt.show()

#@plots a bar graph where y = value for that x=month
#@takes in a dict {k:v} = {month : value}
#This is used by multiple functions thus we have **kwargs
#**kwargs
#   @title='something' sets the title
#   @time='something(seconds)' sets the ylabel
def plotBarGraph_MessagesPerMonth(this, **kwargs):
    dates = [ k for k in this ]
    values = [ v for k, v in this.items() ]
    maxV = max(values)
    if (maxV == 0):
        print("Max value was 0.0, no graph to show :(")
        return None
    
    colors = getColors(len(this),True)
    plt.figure(figsize=(12, 9))
    title = kwargs['title'] if len(kwargs) > 0 else "Messages per Month"
    ylabel = kwargs['time'] if len(kwargs) > 0 else "Messages"
    
    plt.xlabel("Months", fontsize=16,rotation=15)
    plt.ylabel(ylabel,fontsize=16)
    plt.title(title)

    ax = plt.subplot(111)    
    ax.spines["top"].set_visible(False)    
    ax.spines["bottom"].set_visible(False)    
    ax.spines["right"].set_visible(False)    
    ax.spines["left"].set_visible(False) 
    
    plt.xticks(np.arange(0, len(this), 1))
    #plt.yticks(np.arange(0, maxV, maxV//20))
    plt.xticks(rotation=30)

    plt.bar(dates, values, color=colors)
    plt.savefig('total.png',transparent=True,dpi=300)
    plt.show()

#@yeah ok this is something
#@plots a bar graph but multiple bars per key in the dict
#@takes in a dict of dicts that must be plotted on the same graph
#@howandwhy? knowing how many participants there are, we know how many bars per value of month we need
#   thus we can pad along the months by the number of participatns and graph the bars for the others
#@example 3 participants, 5 months. That means 3 bars for every month
#   we create a list and append 2 empty strings after every month.
#   when we plot those lists together the month name will only show under the first bar for that month
#   it works, not elegant in the slightest but it works and it's quite pleasing to look at
#@someday I'll come back to this
def plotBarGraph_MessagesPerMonthPerParticipant(this, pList):
    #this whole thing is a mess but I got tired
    colors = ['#F3B562', '#F06060'] if len(pList) <=2 else getColors(len(pList),False)
    plt.figure(figsize=(12, 9))    
    plt.title("Messages Per Month Per Participant")    
    ax = plt.subplot(1,1,1)    
    ax.spines["top"].set_visible(False)    
    ax.spines["bottom"].set_visible(False)    
    ax.spines["right"].set_visible(False)    
    ax.spines["left"].set_visible(False) 

    plt.xlabel("Dates")
    plt.ylabel("Messages Sent")
    tempdates = [k for k,v in this.items() for i in range(len(pList))]
    tempvalues = [v for a,b in this.items() for k,v in b.items()]
    dates = list()
    values = list()
    i=0
    for x in range(len(tempdates)): #one loop, both lists are the same size
        if (i==len(pList)):
            dates.append('')
            values.append('')
            i=0
        i+=1
        dates.append(tempdates[x])
        values.append(tempvalues[x])

    for p in pList: #plotting the bars of each participant
        #fist bar will be at their pListindexPoint, ends possibly at the end, and with step the length
        #of the participants list+1 since that's how many bars will be ahead of it +1 empty space
        #yes it's a mess
        for i in range(pList.index(p),len(dates),len(pList)+1): 
            plt.bar(i, values[i], width=1,color=colors[pList.index(p)])
    
    plt.xticks(np.arange(0,len(dates),len(pList)+1),dates[::len(pList)+1],rotation=30)
    from matplotlib.lines import Line2D
    customLegend = [Line2D([0], [0], color=colors[i],lw=4) for i in range(len(pList))]
    ax.legend(customLegend, pList)
    plt.tight_layout()
    plt.show()
   
    #plt.bar(range(len(this)*2), list(this.))

#@plots is used as a general perMonth plotting function, just throw a dict at it and a title and it'll plot it
#**kwargs
#   'title'= sets the title, requires string
def plotBarGraph_AveragePerMonth_General(this,**kwargs):
    colors = getColors(len(this),True)
    title = "Average " +kwargs['title']
    title += " Per Month"
    plt.figure(figsize=(12, 9))
    plt.xlabel("Months", fontsize=16)
    plt.ylabel(kwargs['title'], fontsize=16)
    plt.title(title)

    ax = plt.subplot(111)    
    ax.spines["top"].set_visible(False)    
    ax.spines["bottom"].set_visible(False)    
    ax.spines["right"].set_visible(False)    
    ax.spines["left"].set_visible(False) 
    
    dates = [ k for k in this]
    values = [ v for k, v in this.items()]

    plt.xticks(np.arange(0, len(this)))
    plt.yticks(np.arange(0,max(values)))
    plt.xticks(rotation=15)

    plt.bar(dates, values, color=colors)
    plt.tight_layout()
    plt.show()