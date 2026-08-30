import { HeroSection } from "@/components/sections/hero-section"
import { PhilosophySection } from "@/components/sections/philosophy-section"
import { FeaturedProductsSection } from "@/components/sections/featured-products-section"
import { TechnologySection } from "@/components/sections/technology-section"
import { GallerySection } from "@/components/sections/gallery-section"
import { CollectionSection } from "@/components/sections/collection-section"
import { EditorialSection } from "@/components/sections/editorial-section"
import { TestimonialsSection } from "@/components/sections/testimonials-section"
import { FooterSection } from "@/components/sections/footer-section"

export default function HomePage() {
  return (
    <main className="-mt-16">
      <HeroSection />
      <PhilosophySection />
      <FeaturedProductsSection />
      <TechnologySection />
      <GallerySection />
      <CollectionSection />
      <EditorialSection />
      <TestimonialsSection />
      <FooterSection />
    </main>
  )
}
