jQuery(document).ready(function($){

/* SVG for D3 dimensions. */
var area_width  = $("#graphRow").width(),
    area_height = $("#graphRow").height(),
    colors = d3.scale.category20();

/* Nodes and links of the graph. */
var nodes = [],
    links = [];

var svg = d3.select('#graphRow')
    .append('svg')
    .attr('class', 'nw_graph')
    .attr('width', area_width)
    .attr('height', area_height);

var gsta;

/* Handles to link and node element groups. */
var nw_paths = svg.append('svg:g').selectAll('.link'),
    nw_wtps = svg.append('svg:g').selectAll('.wtp'),
    nw_sta = svg.append('svg:g').selectAll('.sta');

/* Introduce force layout in the graph. */
var force = d3.layout.force()
    .size([area_width, area_height])
    .charge(-400)
    .linkDistance(60)
    .on("tick", tick);

/* Introduce drag event. */
var drag = force.drag()
    .on("dragstart", dragstart);

/* Define 'div' for tooltips */
var tp_div = d3.select('body')
    .append('div')
    .attr('class', 'tooltip')
    .style('opacity', 0);

fetchSignalData(tenant_id);

function fetchSignalData(tenant_id) {

    setTimeout(function () {

        $.getJSON("/api/v1/tenants/" + tenant_id + "/components/empower.apps.wifiloadbalancing.wifiloadbalancing", function(data) {
            /* Process the data here after receiving from app.*/
            if (data == null) {
                return;
            }

            var graph_data = data['graphData']

            var existing_nodes = nodes.slice(0);

            links.splice(0, links.length);
            nodes.splice(0, nodes.length);

            /* Iterate through already existing nodes. */
            for (var k in existing_nodes) {
                /* Existing node. */
                var en = existing_nodes[k];

                for (var i in graph_data.nodes) {
                    /* Node from API JSON result. */
                    var n = graph_data.nodes[i];

                    if (en.node_id === n.node_id && en.entity === n.entity) {
                        var node = {
                            id: n.id,
                            node_id: n.node_id,
                            entity: n.entity,
                            tooltip: n.tooltip,
                            x: en.x,
                            y: en.y,
                            fixed: en.fixed
                           };
                        nodes.push(node);
                        graph_data.nodes.splice(i, 1);
                        break;
                    }
                }
            }

            /* Whatever nodes remains in graph_data should be added to nodes. */
            for (var i in graph_data.nodes) {
                var n = graph_data.nodes[i];
                var node = {
                            id: n.id,
                            node_id: n.node_id,
                            entity: n.entity,
                            tooltip: n.tooltip,
                            x: n.x,
                            y: (area_height - n.y),
                            fixed: true
                           };
                nodes.push(node);
            }

            /* Add links from graph_data. */
            for (var i in graph_data.links) {
                var l = graph_data.links[i];

                var source, target;

                for (var m in nodes) {
                    if (nodes[m].id == l.src) {
                        source = nodes[m];
                    }
                    if (nodes[m].id == l.dst) {
                        target = nodes[m];
                    }
                }

                var link = {
                    source: source,
                    target: target,
                    rssi: l.rssi,
                    color: l.color,
                    width: l.width,
                    entity: l.entity,
                    channel: l.channel,
                    tx_bps: l.tx_bps,
                    rx_bps: l.rx_bps
                }
                links.push(link);
            }

            updateSignalGraph();
            fetchSignalData(tenant_id);
        });

    }, 2000);
}

/* Update graph. */
function updateSignalGraph() {

    var g_nodes = nodes.slice(0);
    var g_links = links.slice(0);

    /* Setting SVG background color to white.*/
    d3.select('svg')
        .style('background-color', '#FFFFFF');

    force
    .nodes(g_nodes)
    .links(g_links);

    nw_paths = nw_paths.data(g_links)

    nw_paths.enter().append('line')
            .attr('class', 'link')
            .style('stroke', function(d) { return d.color; })
            .style('stroke-width', function(d) { return d.width; })
            .classed('neigh_cell', function(d) { return (d.width == 4); });

    nw_paths.on("mouseover", function(d) {
                tp_div.transition()
                    .duration(500)
                    .style("opacity", 0);
                tp_div.transition()
                    .duration(200)
                    .style("opacity", .9);
                tt_str = "<p>" + "Channel" + ": " + d.channel;
                tt_str = tt_str + "<br>" + "RSSI" + ": " + d.rssi;
                tt_str = tt_str + "<br>" + "Tx. Bps" + ": " + d.tx_bps;
                tt_str = tt_str + "<br>" + "Rx. Bps" + ": " + d.rx_bps;
                tt_str = tt_str + "</p>";
                tp_div .html(tt_str)
                    .style("left", (d3.event.pageX) + "px")
                    .style("top", (d3.event.pageY - 28) + "px");
            });

    nw_paths.style('stroke', function(d) { return d.color; })
            .style('stroke-width', function(d) { return d.width; })
            .classed('neigh_cell', function(d) { return (d.width == 4); });

    nw_paths.exit().remove();

    nw_wtps = nw_wtps.data(g_nodes.filter(function(d) {
                                            return d.entity === "wtp";
                                        }),
                                        function(d) {
                                            return d.id;
                                        });

    nw_wtps.enter()
            .append('svg:image')
            .attr('class', 'wtp')
            .attr('xlink:href', "/static/apps/signalgraph/wifi.png")
            .attr('width', 40)
            .attr('height', 40)
            .on("dblclick", dblclick)
            .call(drag);

    nw_wtps.on("mouseover", function(d) {
                tp_div.transition()
                    .duration(500)
                    .style("opacity", 0);
                tp_div.transition()
                    .duration(200)
                    .style("opacity", .9);
                tp_div .html(d.tooltip + ": " + d.node_id)
                    .style("left", (d3.event.pageX) + "px")
                    .style("top", (d3.event.pageY - 28) + "px");
            });

    nw_wtps.attr('xlink:href', "/static/apps/signalgraph/wifi.png")
            .attr('width', 40)
            .attr('height', 40);

    nw_wtps.exit().remove();

    nw_sta = nw_sta.data(g_nodes.filter(function(d) {
                                        return d.entity === "sta";
                        }),
                        function(d) {
                                    return d.id;
                        });

    gsta = nw_sta.enter()
        .append('svg:g')
        .attr('class', 'sta');

    gsta.append('svg:circle')
        .attr('r', 13)
        .style('fill', function(d) { return colors(d.id); })
        .style('stroke', function(d) { return d3.rgb(colors(d.id)).darker().toString(); })
        .style('stroke-width', '2.5px');

    gsta.append('svg:text')
        .attr('x', 0)
        .attr('y', 4)
        .attr('class', 'node_id')
        .text(function(d) {
            return "STA";
        });

    gsta.on("mouseover", function(d) {
            tp_div.transition()
                .duration(500)
                .style("opacity", 0);
            tp_div.transition()
                .duration(200)
                .style("opacity", .9);
            tp_div .html(d.tooltip + ": " + d.node_id)
                .style("left", (d3.event.pageX) + "px")
                .style("top", (d3.event.pageY - 28) + "px");
        });

    gsta.on("dblclick", dblclick)
        .call(drag);

    gsta.selectAll('circle')
        .style('fill', function(d) { return colors(d.id); })
        .style('stroke', function(d) { return d3.rgb(colors(d.id)).darker().toString(); })
        .style('stroke-width', '2.5px');

    nw_sta.exit().remove();

    force.start();
}

function tick() {

    nw_paths.attr("x1", function(d) {
                    return d.source.x;
            })
            .attr("y1", function(d) {
                    return d.source.y;
            })
            .attr("x2", function(d) {
                    return d.target.x;
            })
            .attr("y2", function(d) {
                    return d.target.y;
            });

    nw_wtps.attr('transform', function(d) {
        return 'translate(' + (d.x - 20) + ',' + (d.y - 20) + ')';
    });

    nw_sta.attr('transform', function(d) {
        return 'translate(' + d.x + ',' + d.y + ')';
    });
}

function dblclick(d) {
    d3.select(this).classed("fixed", d.fixed = false);
}

function dragstart(d, i) {
    d3.select(this).classed("fixed", d.fixed = true);
}

});

