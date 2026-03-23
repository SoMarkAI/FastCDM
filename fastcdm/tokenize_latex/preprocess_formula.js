const path = require('path');
var katex = require(path.join(__dirname,"third_party/katex/katex.js"))
options = require(path.join(__dirname,"third_party/katex/src/Options.js"))
var readline = require('readline');
var rl = readline.createInterface({
    input: process.stdin,
    output: process.stdout,
    terminal: false
});


rl.on('line', function(line){
    a = line
    if (line[0] == "%") {
        line = line.substr(1, line.length - 1);
    }
    // 用占位符保护已转义的 \%，仅去除未转义的 %（LaTeX 注释），再还原 \%
    line = line.replace(/\\%/g, '\x00PCT\x00');
    line = line.split('%')[0];
    line = line.replace(/\x00PCT\x00/g, '\\%');

    line = line.split('\\~').join(' ');
    
    for (var i = 0; i < 300; i++) {
        line = line.replace(/\\>/, " ");
        line = line.replace('$', ' ');
        line = line.replace(/\\label{.*?}/, "");
    }

    if (line.indexOf("matrix") == -1 && line.indexOf("cases")==-1 &&
        line.indexOf("array")==-1 && line.indexOf("begin")==-1)  {
        for (var i = 0; i < 300; i++) {
            line = line.replace(/\\\\/, "\\,");
        }
    }
    

    line = line + " "
    // global_str：由 parser.js 构建的分词结果；norm_str：由下方渲染器构建的规范化结果
    try {
    

        if (process.argv[2] == "tokenize") {
            var tree = katex.__parse(line, {});
            console.log(global_str.replace(/\\label { .*? }/, ""));
        } else {
            for (var i = 0; i < 300; ++i) {
                line = line.replace(/{\\rm/, "\\mathrm{");
                line = line.replace(/{ \\rm/, "\\mathrm{");
                line = line.replace(/\\rm{/, "\\mathrm{");
            }

            var tree = katex.__parse(line, {});
            buildExpression(tree, new options({}));            
            for (var i = 0; i < 300; ++i) {
                norm_str = norm_str.replace('SSSSSS', '$');
                norm_str = norm_str.replace(' S S S S S S', '$');
            }
            console.log(norm_str.replace(/\\label { .*? }/, ""));
        }
    } catch (e) {
        console.error(line);
        console.error(norm_str);
        console.error(e);
        console.log();
    }
    global_str = ""
    norm_str = ""
})



// LaTeX AST → LaTeX 渲染器（基于 KaTeX AST→MathML 修改而来）
norm_str = ""

var groupTypes = {};

groupTypes.mathord = function(group, options) {
    if (options.font == "mathrm"){
        for (i = 0; i < group.value.length; ++i ) {
            if (group.value[i] == " ") {
                norm_str = norm_str + group.value[i] + "\; ";
            } else {
                norm_str = norm_str + group.value[i] + " ";
            }
        }
    } else {
        norm_str = norm_str + group.value + " ";
    }
};

groupTypes.textord = function(group, options) {
    norm_str = norm_str + group.value + " ";
};

groupTypes.bin = function(group) {
    norm_str = norm_str + group.value + " ";
};

groupTypes.rel = function(group) {
    norm_str = norm_str + group.value + " ";
};

groupTypes.open = function(group) {
    norm_str = norm_str + group.value + " ";
};

groupTypes.close = function(group) {
    norm_str = norm_str + group.value + " ";
};

groupTypes.inner = function(group) {
    norm_str = norm_str + group.value + " ";
};

groupTypes.punct = function(group) {
    norm_str = norm_str + group.value + " ";
};

groupTypes.ordgroup = function(group, options) {
    norm_str = norm_str + "{ ";

    buildExpression(group.value, options);

    norm_str = norm_str +  "} ";
};

groupTypes.text = function(group, options) {
    
    norm_str = norm_str + "\\mathrm { ";

    buildExpression(group.value.body, options);
    norm_str = norm_str + "} ";
};

groupTypes.color = function(group, options) {
    var inner = buildExpression(group.value.value, options);

    var node = new mathMLTree.MathNode("mstyle", inner);

    node.setAttribute("mathcolor", group.value.color);

    return node;
};

groupTypes.supsub = function(group, options) {
    buildGroup(group.value.base, options);

    if (group.value.sub) {
        norm_str = norm_str + "_ ";
        if (group.value.sub.type != 'ordgroup') {
            norm_str = norm_str + " { ";
            buildGroup(group.value.sub, options);
            norm_str = norm_str + "} ";
        } else {
            buildGroup(group.value.sub, options);
        }
        
    }

    if (group.value.sup) {
        norm_str = norm_str + "^ ";
        if (group.value.sup.type != 'ordgroup') {
            norm_str = norm_str + " { ";
            buildGroup(group.value.sup, options);
            norm_str = norm_str + "} ";
        } else {
            buildGroup(group.value.sup, options);
        }
    }

};

groupTypes.genfrac = function(group, options) {
    if (!group.value.hasBarLine) {
        norm_str = norm_str + "\\binom ";
    } else {
        norm_str = norm_str + "\\frac ";
    }
    buildGroup(group.value.numer, options);
    buildGroup(group.value.denom, options);

};

groupTypes.array = function(group, options) {
    norm_str = norm_str + "\\begin{array} { ";
    if (group.value.cols) {
        group.value.cols.map(function(start) {
            if (start && start.align) {
                norm_str = norm_str + start.align + " ";}});
    } else {
        group.value.body[0].map(function(start) {
            norm_str = norm_str + "l ";
        } );
    }
    norm_str = norm_str + "} ";
    group.value.body.map(function(row) {
        if (row.some(cell => cell.value.length > 0)) { // 原始代码：if (row[0].value.length > 0)
            out = row.map(function(cell) {
                buildGroup(cell, options);
                if (norm_str.length > 4 
                    && norm_str.substring(norm_str.length-4, norm_str.length) == "{ } ") {
                    norm_str = norm_str.substring(0, norm_str.length-4) ;
                }
                norm_str = norm_str + "& ";
            });
            norm_str = norm_str.substring(0, norm_str.length-2) + "\\\\ ";
        }
    }); 
    norm_str = norm_str + "\\end{array} ";
};

groupTypes.sqrt = function(group, options) {
    var node;
    if (group.value.index) {
        norm_str = norm_str + "\\sqrt [ ";
        buildExpression(group.value.index.value, options);
        norm_str = norm_str + "] ";
        buildGroup(group.value.body, options);
    } else {
        norm_str = norm_str + "\\sqrt ";
        buildGroup(group.value.body, options);
    }
};

groupTypes.leftright = function(group, options) {



    norm_str = norm_str + "\\left" + group.value.left + " ";
    buildExpression(group.value.body, options);
    norm_str = norm_str + "\\right" + group.value.right + " ";
};

groupTypes.accent = function(group, options) {
    if (group.value.base.type != 'ordgroup') {
        norm_str = norm_str + group.value.accent + " { ";
        buildGroup(group.value.base, options);
        norm_str = norm_str + "} ";
    } else {
        norm_str = norm_str + group.value.accent + " ";
        buildGroup(group.value.base, options);
    }
};

groupTypes.spacing = function(group) {
    var node;
    if (group.value == " ") {
        norm_str = norm_str + "~ ";
    } else {
        norm_str = norm_str + group.value + " ";
    }
    return node;
};

groupTypes.op = function(group) {
    var node;

    if (group.value.symbol) {
        // 直接输出符号
        norm_str = norm_str + group.value.body + " ";

    } else {
        if (group.value.limits == false) {
            norm_str = norm_str + "\\\operatorname { ";
        } else {
            norm_str = norm_str + "\\\operatorname* { ";
        }
        for (i = 1; i < group.value.body.length; ++i ) {
            norm_str = norm_str + group.value.body[i] + " ";
        }
        norm_str = norm_str + "} ";
    }
};

groupTypes.katex = function(group) {
    var node = new mathMLTree.MathNode(
        "mtext", [new mathMLTree.TextNode("KaTeX")]);

    return node;
};



groupTypes.font = function(group, options) {
    var font = group.value.font;
    if (font == "mbox" || font == "hbox") {
        font = "mathrm";
    }
    norm_str = norm_str + "\\" + font + " ";
    buildGroup(group.value.body, options.withFont(font));    
};

groupTypes.delimsizing = function(group) {
    var children = [];
    norm_str = norm_str + group.value.funcName + " " + group.value.value + " ";
};

groupTypes.styling = function(group, options) {
    norm_str = norm_str + " " + group.value.original + " ";
    buildExpression(group.value.value, options);

};

groupTypes.sizing = function(group, options) {

    if (group.value.original == "\\rm") {
        norm_str = norm_str + "\\mathrm { "; 
        buildExpression(group.value.value, options.withFont("mathrm"));
        norm_str = norm_str + "} ";
    } else {
        norm_str = norm_str + " " + group.value.original + " ";
        buildExpression(group.value.value, options);
    }
};

groupTypes.overline = function(group, options) {
    norm_str = norm_str + "\\overline { ";
    
    buildGroup(group.value.body, options);
    norm_str = norm_str + "} ";
    norm_str = norm_str;

};

groupTypes.underline = function(group, options) {
    norm_str = norm_str + "\\underline { ";
    buildGroup(group.value.body, options);
    norm_str = norm_str + "} ";

    norm_str = norm_str;

};

groupTypes.rule = function(group) {
    norm_str = norm_str + "\\rule { "+group.value.width.number+" "+group.value.width.unit+"  } { "+group.value.height.number+" "+group.value.height.unit+ " } ";

};

groupTypes.llap = function(group, options) {
    norm_str = norm_str + "\\llap ";
    buildGroup(group.value.body, options);
};

groupTypes.rlap = function(group, options) {
    norm_str = norm_str + "\\rlap ";
    buildGroup(group.value.body, options);

};

groupTypes.phantom = function(group, options, prev) {
    norm_str = norm_str + "\\phantom { ";
    buildExpression(group.value.value, options);
    norm_str = norm_str + "} ";

};

/**
 * 遍历节点列表并依次构建，将结果追加到 norm_str。
 */
var buildExpression = function(expression, options) {
    var groups = [];
    for (var i = 0; i < expression.length; i++) {
        var group = expression[i];
        buildGroup(group, options);
    }
};

/**
 * 根据节点类型调用对应的 groupTypes 处理函数，将结果追加到 norm_str。
 */
var buildGroup = function(group, options) {
    if (groupTypes[group.type]) {
        groupTypes[group.type](group, options);
    } else {
        throw new ParseError(
            "Got group of unknown type: '" + group.type + "'");
    }
};


