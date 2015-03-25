<?xml version="1.0" encoding="utf-8"?>
<xsl:stylesheet version="1.0" xmlns:xsl="http://www.w3.org/1999/XSL/Transform">

<xsl:output method="text" omit-xml-declaration="yes" indent="no"/>

<xsl:template match="/valgrindoutput">
<xsl:if test="error | suppcounts/pair"><!--
-->Valgrind <xsl:value-of select="tool" /> results<xsl:if test="usercomment"> - <xsl:value-of select="usercomment" />
<xsl:text>
</xsl:text>
</xsl:if>
<xsl:if test="error/what">
======= Errors =======
<xsl:for-each select="error[what]">
<xsl:value-of select="kind" />: <xsl:value-of select="what" /><xsl:text>
</xsl:text></xsl:for-each>
</xsl:if>
<xsl:if test="error/xwhat/leakedbytes">
==== Leaked Memory ====
<xsl:if test="error[kind='Leak_DefinitelyLost']/xwhat/leakedbytes"><!--
--> Definately Lost: <xsl:value-of select="sum(error[kind='Leak_DefinitelyLost']/xwhat/leakedbytes | error[kind='Leak_IndirectlyLost']/xwhat/leakedbytes)" /> bytes
</xsl:if>
<xsl:if test="error[kind='Leak_PossiblyLost']/xwhat/leakedbytes"><!--
-->   Possibly Lost: <xsl:value-of select="sum(error[kind='Leak_PossiblyLost']/xwhat/leakedbytes)" /> bytes
</xsl:if>
<xsl:if test="error[kind='Leak_StillReachable']/xwhat/leakedbytes"><!--
-->Reachable Memory: <xsl:value-of select="sum(error[kind='Leak_StillReachable']/xwhat/leakedbytes)" /> bytes
</xsl:if>
</xsl:if>
<xsl:if test="suppcounts/pair">
==== Suppressions ====
<xsl:for-each select="suppcounts/pair">
<xsl:value-of select="count" /> - <xsl:value-of select="name"/><xsl:text>
</xsl:text></xsl:for-each>
</xsl:if>
</xsl:if>
</xsl:template>

</xsl:stylesheet>
