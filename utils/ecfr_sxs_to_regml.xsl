<?xml version="1.0"?>
<xsl:stylesheet version="1.0" xmlns:xsl="http://www.w3.org/1999/XSL/Transform">
    <!-- 
        Convert a fragment of eCFR XML containing section-by-section
        analysis to a RegML <analysis> element. 

        This stylesheet assumes the input file to be transformed has 
        one top-level element and ONLY contains eCFR XML for the 
        section-by-section anlaysis.

        SxS should look something like this:

        <my_root_element_that_doesnt_matter>
            <HD SOURCE="HD1">V. Section-by-Section Analysis</HD>
            <HD SOURCE="HD2">A. Regulation Foo</HD>
            <HD SOURCE="HD3">Section 1234.11 A particular section</HD>
            <P>Some insightful analysis<SU>1</SU><FTREF/></P>
            <FTNT>
                <P><SU>1</SU>A footnote</P>
            </FTNT>
        </my_root_element_that_doesnt_matter>

        Use this stylesheet with xsltproc:
            xsltproc -o my_output_file.xml utils/ecfr_sxs_to_regml.xsl my_ecfr_sxs_fragment.xml
    -->

    <xsl:output method="xml" indent="yes" encoding="UTF-8"/>

    <xsl:template match="/">
        <analysis>
            <xsl:apply-templates select="//HD[@SOURCE='HD3']"/>
        </analysis>
    </xsl:template>

    <!-- Ignore HD1 and HD2 headers -->
    <xsl:template match="HD[@SOURCE='HD1']"></xsl:template>
    <xsl:template match="HD[@SOURCE='HD2']"></xsl:template>
    <xsl:template match="HD[@SOURCE='HD3']">
        <xsl:variable name="header" select="."/>
        <analysisSection>
            <title><xsl:value-of select="."/></title>
            <!-- These are flat, but we need to infer some heirarchy.
                 Apply to all siblings who aren't also HD3s. We'll have 
                 to manually fix the heirarchy later. -->
            <xsl:apply-templates select="following-sibling::P[preceding-sibling::HD[@SOURCE='HD3'][1] = $header]"/>
        </analysisSection>
    </xsl:template>

    <xsl:template match="P[not(ancestor::FTNT)]">
        <analysisParagraph>
            <xsl:apply-templates select="SU|node()"/>
        </analysisParagraph>
    </xsl:template>

    <xsl:template match="SU[not(ancestor::FTNT/P)]">
        <xsl:variable name="parent" select="parent"/>
        <xsl:variable name="footnote_ref" select="text()"/>
        <footnote>
            <xsl:attribute name="ref">
                <xsl:value-of select="." />
            </xsl:attribute>
            <!-- Footnotes are weird in eCFR XML. The text of this
                 footnote is in an FTNT/P element that follows this 
                 element's parent, and which has a matching SU element 
                 value -->
            <xsl:apply-templates select="../following-sibling::FTNT[P/SU[text() = $footnote_ref]]"/>
        </footnote>
    </xsl:template>
    <xsl:template match="SU[ancestor::FTNT/P]"></xsl:template>

    <!-- Ignore these, we pick up footnotes based on the SU tag -->
    <xsl:template match="FTREF"></xsl:template>
    <xsl:template match="FTNT">
        <xsl:apply-templates select="@*|node()"/>
    </xsl:template>

</xsl:stylesheet>
