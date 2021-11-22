<?xml version="1.0" encoding="UTF-8"?>

<!--
     Stylesheet to provide a condensed view of a NeXus NXDL specification.
     (see https://github.com/nexusformat/definitions/issues/181)

     The nxdlformat.xsl stylesheets differ between the directories 
     because of the rule regarding either /definition/NXentry or
     /definition/NXsubentry for application and contributed definitions.
     (see https://github.com/nexusformat/definitions/issues/179)

     Modify <xsl:template match="nx:definition">...</xsl:template> 
     for each directory.

line breaks are VERY TRICKY here, be careful how you edit!
-->

<xsl:stylesheet xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
     xmlns:nx="http://definition.nexusformat.org/nxdl/3.1" version="1.0">

     <xsl:output method="text"/>
     <xsl:variable name="indent_step" select="'  '"/>


     <xsl:template match="/">
          <xsl:apply-templates select="nx:definition"/>
     </xsl:template>
     

     <!--
          Modify ONLY this section for each directory:
          base_classes/nxdlformat.xsl             no rule for NXentry or NXsubentry
          applications/nxdlformat.xsl             required rule for NXentry or NXsubentry
          contributed_definitions/nxdlformat.xsl  optional rule for NXentry or NXsubentry
     -->
     <xsl:template match="nx:definition">
          <xsl:call-template name="showClassName"/>
          <xsl:call-template name="startFieldsGroups"/>
     </xsl:template>
     

     <!-- ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++ -->
     <!-- +++    From this point on, the code is the same for,       +++ -->
     <!-- +++    base_classes applications/, and contributed/        +++ -->
     <!-- ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++ -->
     
     
     <xsl:template match="nx:field">
          <xsl:param name="indent"/>
          <xsl:value-of select="$indent"/><xsl:value-of select="@name"/>:<xsl:choose>
               <xsl:when test="count(@type)"><xsl:value-of select="@type"
               /><xsl:apply-templates select="nx:dimensions"
                    ><xsl:sort select="@name"/></xsl:apply-templates></xsl:when>
               <xsl:otherwise>NX_CHAR</xsl:otherwise>
          </xsl:choose>
          <xsl:text><!-- tricky line break here -->
</xsl:text><!--
--><xsl:apply-templates select="nx:attribute">
               <xsl:with-param name="indent">
                    <xsl:value-of select="$indent"/>
                    <xsl:value-of select="$indent_step"/>
               </xsl:with-param>
          </xsl:apply-templates>
     </xsl:template>
     
     
     <xsl:template match="nx:dimensions"><!--
     -->[<xsl:apply-templates select="nx:dim"/>]<!--
          --></xsl:template>
     
     
     <xsl:template match="nx:dim">
          <xsl:choose>
               <xsl:when test="position()=1"><xsl:value-of select="@value"/></xsl:when>
               <xsl:otherwise>,<xsl:value-of select="@value"/></xsl:otherwise>
          </xsl:choose>
     </xsl:template>
     
     
     <xsl:template match="nx:link">
          <xsl:param name="indent"/>
          <xsl:value-of select="$indent"/><xsl:value-of select="@name"/><xsl:text
               > --> </xsl:text><xsl:value-of select="@target"/><xsl:text><!-- tricky line break here -->
</xsl:text>
     </xsl:template>
     
     
     <xsl:template match="nx:attribute">
          <xsl:param name="indent"/>
          <xsl:value-of select="$indent"/>@<xsl:value-of select="@name"/>
          <xsl:text><!-- tricky line break here -->
</xsl:text>
     </xsl:template>
     
     
     <xsl:template match="nx:group">
          <xsl:param name="indent"/>
          <xsl:value-of select="$indent"/>
          <xsl:if test="count(@name)"><xsl:value-of select="@name"/>:</xsl:if>
          <xsl:value-of select="@type"/>
          <xsl:text><!-- tricky line break here -->
</xsl:text><!--
--><xsl:apply-templates select="nx:attribute">
               <xsl:with-param name="indent">
                    <xsl:value-of select="$indent"/>
                    <xsl:value-of select="$indent_step"/>
               </xsl:with-param>
          </xsl:apply-templates>
          <xsl:apply-templates select="nx:field">
               <xsl:with-param name="indent">
                    <xsl:value-of select="$indent"/>
                    <xsl:value-of select="$indent_step"/>
               </xsl:with-param>
               <xsl:sort select="@name"/>
          </xsl:apply-templates>
          <xsl:apply-templates select="nx:link">
               <xsl:with-param name="indent">
                    <xsl:value-of select="$indent"/>
                    <xsl:value-of select="$indent_step"/>
               </xsl:with-param>
               <xsl:sort select="@name"/>
          </xsl:apply-templates>
          <xsl:apply-templates select="nx:group">
               <xsl:with-param name="indent">
                    <xsl:value-of select="$indent"/>
                    <xsl:value-of select="$indent_step"/>
               </xsl:with-param>
               <xsl:sort select="@type"/>
          </xsl:apply-templates>
     </xsl:template>
     
     
     <xsl:template name="startFieldsGroups">
          <xsl:apply-templates select="nx:attribute">
               <xsl:with-param name="indent">
                    <xsl:value-of select="$indent_step"/>
               </xsl:with-param>
          </xsl:apply-templates>
          <xsl:choose>
               <!-- Two ways to render.  
                    1=1: write fields, links, then groups, each sorted alphabetically
                    1!=1: order of appearance in NXDL
               -->
               <xsl:when test="1=1"><!-- write fields, links, then groups -->
                    <xsl:apply-templates select="nx:field">
                         <xsl:with-param name="indent"><xsl:value-of select="$indent_step"/></xsl:with-param>
                         <xsl:sort select="@name"/>
                    </xsl:apply-templates>
                    <xsl:apply-templates select="nx:link">
                         <xsl:with-param name="indent"><xsl:value-of select="$indent_step"/></xsl:with-param>
                         <xsl:sort select="@name"/>
                    </xsl:apply-templates>
                    <xsl:apply-templates select="nx:group">
                         <xsl:with-param name="indent"><xsl:value-of select="$indent_step"/></xsl:with-param>
                         <xsl:sort select="@type"/>
                    </xsl:apply-templates>
               </xsl:when>
               <xsl:otherwise><!-- write in order of appearance in NXDL -->
                    <xsl:apply-templates select="nx:field|nx:link|nx:group">
                         <xsl:with-param name="indent"><xsl:value-of select="$indent_step"/></xsl:with-param>
                         <xsl:sort select="@type"/>
                    </xsl:apply-templates>
               </xsl:otherwise>
          </xsl:choose>
     </xsl:template>
     
     
     <xsl:template name="showClassName">
          <xsl:value-of select="@name"/> (<xsl:choose>
               <xsl:when test="@category='base'">base class</xsl:when>
               <xsl:when test="@category='application'">application definition</xsl:when>
               <xsl:when test="@category='contributed'">contributed definition</xsl:when>
          </xsl:choose>)<xsl:text><!-- tricky line break here -->
</xsl:text></xsl:template>
     
</xsl:stylesheet>

<!--
     # NeXus - Neutron and X-ray Common Data Format
     # 
     # Copyright (C) 2008-2021 NeXus International Advisory Committee (NIAC)
     # 
     # This library is free software; you can redistribute it and/or
     # modify it under the terms of the GNU Lesser General Public
     # License as published by the Free Software Foundation; either
     # version 3 of the License, or (at your option) any later version.
     #
     # This library is distributed in the hope that it will be useful,
     # but WITHOUT ANY WARRANTY; without even the implied warranty of
     # MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
     # Lesser General Public License for more details.
     #
     # You should have received a copy of the GNU Lesser General Public
     # License along with this library; if not, write to the Free Software
     # Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
     #
     # For further information, see http://www.nexusformat.org
-->
