<?xml version="1.0" encoding="utf-8"?>
<xsl:stylesheet version="1.0" xmlns:xsl="http://www.w3.org/1999/XSL/Transform">

<xsl:output method="text" omit-xml-declaration="yes" indent="no"/>

<xsl:template name="newline"><xsl:text>
</xsl:text></xsl:template>

<xsl:template name="mainheader"><!--
	-->Valgrind <xsl:value-of select="tool" /> results<xsl:if test="usercomment"> - <xsl:value-of select="usercomment" /></xsl:if><!--
	--><xsl:call-template name="newline" /><!--
--></xsl:template>

<xsl:template name="padleft"><!--
	--><xsl:param name="str" /><!--
	--><xsl:param name="width" select="20" /><!--
	--><xsl:choose><!--
		--><xsl:when test="string-length($str) &lt; $width"><!--
			--><xsl:call-template name="padleft"><!--
				--><xsl:with-param name="str"><xsl:text> </xsl:text><xsl:value-of select="$str"/></xsl:with-param><!--
				--><xsl:with-param name="width" select="$width" /><!--
			--></xsl:call-template><!--
		--></xsl:when><!--
		--><xsl:otherwise><!--
			--><xsl:value-of select="$str" /><!--
		--></xsl:otherwise><!--
	--></xsl:choose><!--
--></xsl:template>

<xsl:template name="errors"><!--
	--><xsl:call-template name="newline" /><!--
	-->================= Errors ==================<!--
	--><xsl:call-template name="newline" /><!--
	--><xsl:for-each select="error[what]"><!--
		--><xsl:call-template name="padleft"><!--
			--><xsl:with-param name="str" select="kind" /><!--
		--></xsl:call-template>: <xsl:value-of select="what"/><!--
		--><xsl:call-template name="newline" /><!--
	--></xsl:for-each><!--
--></xsl:template>

<xsl:template name="leakedmemory"><!--
	--><xsl:call-template name="newline" /><!--
	-->============== Leaked Memory ==============<!--
	--><xsl:call-template name="newline" /><!--
	--><xsl:if test="error[kind='Leak_DefinitelyLost']/xwhat/leakedbytes"><!--
		-->     Definately Lost: <xsl:value-of select="sum(error[kind='Leak_DefinitelyLost']/xwhat/leakedbytes | error[kind='Leak_IndirectlyLost']/xwhat/leakedbytes)" /> bytes<!--
		--><xsl:call-template name="newline" /><!--
	--></xsl:if><!--
	--><xsl:if test="error[kind='Leak_PossiblyLost']/xwhat/leakedbytes"><!--
		-->       Possibly Lost: <xsl:value-of select="sum(error[kind='Leak_PossiblyLost']/xwhat/leakedbytes)" /> bytes<!--
		--><xsl:call-template name="newline" /><!--
	--></xsl:if><!--
	--><xsl:if test="error[kind='Leak_StillReachable']/xwhat/leakedbytes"><!--
		-->    Reachable Memory: <xsl:value-of select="sum(error[kind='Leak_StillReachable']/xwhat/leakedbytes)" /> bytes<!--
		--><xsl:call-template name="newline" /><!--
	--></xsl:if><!--
--></xsl:template>

<xsl:template name="suppressions"><!--
	--><xsl:call-template name="newline" /><!--
	-->============== Suppressions ===============<!--
	--><xsl:call-template name="newline" /><!--
	--><xsl:for-each select="suppcounts/pair"><!--
		--><xsl:call-template name="padleft"><!--
			--><xsl:with-param name="str" select="count" /><!--
		--></xsl:call-template>: <xsl:value-of select="name"/><!--
		--><xsl:call-template name="newline" /><!--
	--></xsl:for-each><!--
--></xsl:template>

<xsl:template match="/valgrindoutput"><!--
	--><xsl:if test="error | suppcounts/pair"><xsl:call-template name="mainheader" /></xsl:if><!--
	--><xsl:if test="error/what"><xsl:call-template name="errors" /></xsl:if><!--
	--><xsl:if test="error/xwhat/leakedbytes"><xsl:call-template name="leakedmemory" /></xsl:if><!--
	--><xsl:if test="suppcounts/pair"><xsl:call-template name="suppressions" /></xsl:if><!--
--></xsl:template>

</xsl:stylesheet>
