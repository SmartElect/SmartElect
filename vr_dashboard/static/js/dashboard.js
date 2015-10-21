// Voter registration dashboard charts
// . D3 and NVD3 included from base template
// . translation table (dashboardTrans) defined in base template

var colorArray = [
        '#FF8B3D', // primary orange
        '#aaaaaa', // morning + grey
        '#f1d900', // morning + yellow
        '#ffa0d0', // morning + pink
        '#ff0023', // morning + red
        '#94689a', // morning + violet
        '#fdd8b1', // morning + tan
        '#08f6c6', // morning + sea foam
        '#960f61', // morning + burgandy
        '#ebc31f', // morning + gold
        '#b6bab2', // morning + dark grey
        '#bf9761', // morning + brown
        '#1c747d', // morning + deep sea
        '#4434c9', // morning + royal blue
        '#402d4b', // morning + dark purple
        '#acb094', // morning + yet another grey
        '#31b4c9', // morning + electric blue
        '#f77324', // morning + astro's original orange
        '#a68626', // morning + brown
        '#cca386', // morning + artificial limb
        '#738272', // morning + rain storm
        '#b15475', // morning + fuscia
        '#e9fb2f', // morning + artificial banana
        '#d27751', // morning + rust
        '#c0c25b', // morning + fool's gold
        '#a69662', // morning + melanoma
        '#d78452', // morning + ron burgandy
        '#f8c585', // morning + silly putty
        '#d3db89', // morning + tri-repetae
        '#75ebaf', // morning + really bright cyan
        '#f99ead', // morning + hot pink
        '#fa7b40', // morning + very red
        '#b1d6b5', // morning + sky blue
        '#f89e73', // morning + muted pink
        '#fbbb4d', // afternoon + primary orange
        '#d1ce87', // afternoon + grey
        '#f5e532', // afternoon + yellow
        '#fcc798', // afternoon + pink
        '#fc7641', // afternoon + red
        '#c8a97b', // afternoon + violet
        '#fde086', // afternoon + tan
        '#7eee90', // afternoon + sea foam
        '#ea7259', // afternoon + burgandy
        '#f5d035', // afternoon + gold
        '#d7c882', // afternoon + dark grey
        '#dcb154', // afternoon + brown
        '#7e9a62', // afternoon + deep sea
        '#906d8c', // afternoon + royal blue
        '#8c6540', // afternoon + dark purple
        '#ccb06a', // afternoon + yet another grey
        '#7bae8b', // afternoon + electric blue
        '#fa7e1e', // afternoon + astro's original orange
        '#c2841c', // afternoon + brown
        '#d9925c', // afternoon + artificial limb
        '#97744d', // afternoon + rain storm
        '#c24c4e', // afternoon + fuscia
        '#eac417', // afternoon + artificial banana
        '#d7572e', // afternoon + rust
        '#c68e35', // afternoon + fool's gold
        '#ad6239', // afternoon + melanoma
        '#d44c2a', // afternoon + ron burgandy
        '#ef8158', // afternoon + silly putty
        '#cc925b', // afternoon + tri-repetae
        '#6e9e80', // afternoon + really bright cyan
        '#ec4f80', // afternoon + hot pink
        '#eb2915', // afternoon + very red
        '#a18089', // afternoon + sky blue
        '#e74647', // afternoon + muted pink
        '#e96121', // dusk + primary orange
        '#bd715c', // dusk + grey
        '#df8607', // dusk + yellow
        '#e5676d', // dusk + pink
        '#e41416', // dusk + red
        '#ad4551', // dusk + violet
        '#e27b5c', // dusk + tan
        '#628766', // dusk + sea foam
        '#cc0b30', // dusk + burgandy
        '#d6670b', // dusk + gold
        '#b95f5b', // dusk + dark grey
        '#bd492d', // dusk + brown
        '#5e323c', // dusk + deep sea
        '#710869', // dusk + royal blue
        '#6b001d', // dusk + dark purple
        '#ab4e49', // dusk + yet another grey
        '#594f6c', // dusk + electric blue
        '#d62301', // dusk + astro's original orange
        '#9d2c01', // dusk + brown
        '#b43f43', // dusk + artificial limb
        '#702437', // dusk + rain storm
        '#9b003b', // dusk + fuscia
        '#c27d07', // dusk + artificial banana
        '#ae1322', // dusk + rust
        '#9c4d2c', // dusk + fool's gold
        '#832633', // dusk + melanoma
        '#a91328', // dusk + ron burgandy
        '#c54c58', // dusk + silly putty
        '#a0605f', // dusk + tri-repetae
        '#436f86', // dusk + really bright cyan
        '#c12388', // dusk + hot pink
        '#c0001f', // dusk + very red
        '#755b96', // dusk + sky blue
        '#bc2455' // dusk + muted pink
    ];

var vrDashboardCharts = (function () {

    function numRegistrationsTooltip(newOrTotalHeading, region, _, numRegistrations, item) {

        function dateFromMilliseconds(ms) {
            // Avoid using d3 time formatting since we need to control the translation.
            var d = new Date(ms);
            return dashboardTrans.months[d.getUTCMonth()] + ' ' + d.getUTCDate() + ', ' + d.getUTCFullYear();
        }

        var x = item.point.x != null ? item.point.x : item.point.label;
        var dateString = dateFromMilliseconds(x);
        var tooltipContent = [];
        tooltipContent.push('<p><strong>' + numRegistrations + '</strong> ' + newOrTotalHeading + '</p>');
        tooltipContent.push('<p>' + dateString + '</p>');
        return(tooltipContent.join('\n'));
    }

    function getTooltipFunction(newOrTotal) {
        return function (region, xAxisLabel, numRegistrations, item) {
            return numRegistrationsTooltip(newOrTotal, region, xAxisLabel, numRegistrations, item);
        };
    }

    function xAxisLabelFromMilliseconds(ms) {
        return d3.time.format.utc('%d/%m')(new Date(ms));
    }

    function disableSubGroupings(data) {
        // Disable visibility of all but first data set (national).
        // The user can click on the legend to enable other groups, such as a region
        // or subconstituency.
        for (var i = 1; i < data.length; i++) {
            data[i].disabled = true;
        }
    }

    function pruneLabels(d){
        var labels = d[0].values.map(function(d){
            var labelText = d.label || d.x;
            return labelText;
        });

        var graph_width = $('#new-registrations-chart').width();
        var label_width = 25;
        var squished_width_per_label = graph_width / labels.length;
        var accumulator = label_width/2;

        for(var i=0; i<labels.length; i++){

            accumulator += squished_width_per_label;
            if(accumulator >= label_width){
                accumulator = label_width - accumulator;
            }else{
                // mark it for removal
                labels[i] = null;
            }
        }
        // remove the null values
        return labels.filter(function(el){ return el; });
    }

    function chartNewRegistrationsWithBars(newRegs) {

        function addMissingDataPoints() {
          // The cumulative chart needs data points for each day, even if there were no
          // registrations. In order to make both charts scroll together, we need to add data points
          // for the newRegs chart as well.
          var firstArray = newRegs[0].values; // time values for all groups the same
          var msPerDay = 1000 * 60 * 60 * 24; // all time values are in this increment
          for (var i = 1; i < firstArray.length; i++) {  // for each data point
            if (firstArray[i - 1].label + msPerDay < firstArray[i].label) {
              // add missing day across all the arrays (e.g., for all offices)
              for (var j = 0; j < newRegs.length; j++) {
                var thisArray = newRegs[j].values;
                thisArray.splice(i, 0, {
                  'label': thisArray[i - 1].label + msPerDay, // one day later
                  'value': 0 // no additional registrations
                });
              }
            }
          }
        }

        disableSubGroupings(newRegs); // only main group (national) enabled by default

        addMissingDataPoints();

        nv.addGraph(function () {
            var chart = nv.models.multiBarChart();

            chart.x(function (d) { return d.label; })
                 .y(function (d) { return d.value; })
                 .forceY([0,10])  // if no registrations, still show 0-10 labels on y axis
                 .staggerLabels(false)
                 .tooltips(true)
                 .reduceXTicks(false)
                 .showLegend(false)
                 .tooltipContent(getTooltipFunction(dashboardTrans['New Registrations']))
                 .transitionDuration(350)
                 .color(colorArray)
                 .groupSpacing(0.1)
                 .stacked(false)
                 .showControls(false);

            chart.xAxis.rotateLabels(-90)
                       .tickValues(pruneLabels)
                       .tickFormat(xAxisLabelFromMilliseconds)
                       .showMaxMin(false);

            chart.yAxis.tickFormat(d3.format(',f'))
                       .showMaxMin(false);
            d3.select('#new-registrations-chart svg')
                .datum(newRegs)
                .call(chart);

            nv.utils.windowResize(chart.update);
            window.newRegistrationsWithBars = chart;
            return chart;
        });
    }

    function chartCumulativeRegistrationsWithLines(cumRegs) {

        function addMissingDataPoints() {
            // The X axis for the cumulative chart is proportional by time, such
            // that extra space is added on the X axis by NVD3 for days with no
            // registrations.
            //
            // Add in the missing days so that X axis labels are generated for days
            // with no registrations.  As the calculation of the chart width is
            // based on the number of entries, adding in the missing entries allows
            // that calculation to account for the space required along the X axis.
            var firstArray = cumRegs[0].values; // time values for all groups the same
            var msPerDay = 1000 * 60 * 60 * 24; // all time values are in this increment
            for (var i = 1; i < firstArray.length; i++) {  // for each data point
                if (firstArray[i - 1].x + msPerDay < firstArray[i].x) {
                    // add missing day across all the arrays (e.g., for all offices)
                    for (var j = 0; j < cumRegs.length; j++) {
                        var thisArray = cumRegs[j].values;
                        thisArray.splice(i, 0, {
                            'x': thisArray[i - 1].x + msPerDay, // one day later
                            'y': thisArray[i - 1].y // no additional registrations
                        });
                    }
                }
            }
        }

        disableSubGroupings(cumRegs); // only main group (national) enabled by default
        addMissingDataPoints();

        nv.addGraph(function () {
            var chart = nv.models.lineChart();
            chart.tooltipContent(getTooltipFunction(dashboardTrans['Total Registrations']))
                 .transitionDuration(350)
                 .showLegend(false)
                 .color(colorArray)
                 .useVoronoi(false); // work around multiple lines having same points (https://github.com/novus/nvd3/issues/330)
            chart.xAxis.showMaxMin(false)
                       .tickFormat(xAxisLabelFromMilliseconds)
                       .tickValues(pruneLabels)
                       .staggerLabels(false)
                       .rotateLabels(-90);

            chart.yAxis.tickFormat(d3.format(',f'));
            d3.select('#cumulative-registrations-chart svg').datum(cumRegs).call(chart);
            nv.utils.windowResize(chart.update);
            window.cumulativeRegistrationsWithLines = chart;
            return chart;
        });
    }

    function addNormalCharts(newRegs, cumRegs) {
        chartNewRegistrationsWithBars(newRegs);
        chartCumulativeRegistrationsWithLines(cumRegs);
    }

    function addWeeklyCharts(newRegs, genderData) {
        chartNewRegistrationsWithBars(newRegs);
        nv.addGraph(function () {
            var chart = nv.models.pieChart();
            chart.showLabels(true)
                 .showLegend(false)
                 .tooltipContent(function (label) {
                    // label should be {Male|Female}: Percentage
                    var fields = label.split(':');
                    tooltipContent = [];
                    tooltipContent.push('<p>'+fields[0]+'</p>');
                    tooltipContent.push('<p>'+dashboardTrans['Gender'] + ': <strong>' + fields[1] + '</strong></p>');
                    return tooltipContent.join('\n');
                 });
            d3.select("#gender-breakdown-chart svg").datum(genderData)
                                                    .transition().duration(350)
                                                    .call(chart);
            return chart;
        });
    }

    return {
        addNormalCharts: addNormalCharts,
        addWeeklyCharts: addWeeklyCharts
    };
} )();
