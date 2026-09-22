from django.core.management.base import BaseCommand
from django.conf import settings
from shop.models import Category,Product,Variant,StoreSettings

# Candidate assortment, not a representation of verified merchant stock.
# Every price below is a planning estimate except specifically sourced references.
GROUPS = [
('Dry fruits & nuts','ఎండు పండ్లు & గింజలు','dry-fruits',[
('California Almonds','కాలిఫోర్నియా బాదం','500 g',600),('Whole Cashews','జీడిపప్పు','500 g',682),('Pistachios','పిస్తా','250 g',380),('Premium Dates','ఖర్జూరాలు','500 g',240),('Golden Raisins','ఎండు ద్రాక్ష','500 g',381),('Dried Figs','అంజీర పండ్లు','250 g',390),('Walnut Kernels','అక్రోటు పప్పు','250 g',420),('Dried Apricots','ఎండిన ఆప్రికాట్ పండ్లు','250 g',300),('Black Raisins','నల్ల ఎండు ద్రాక్ష','250 g',190),('Green Raisins','పచ్చ ఎండు ద్రాక్ష','250 g',200),('Medjool Dates','మెడ్జూల్ ఖర్జూరాలు','250 g',450),('Ajwa Dates','అజ్వా ఖర్జూరాలు','250 g',390),('Salted Cashews','ఉప్పు జీడిపప్పు','250 g',320),('Roasted Almonds','వేయించిన బాదం','250 g',330),('Mixed Dry Fruits','మిశ్రమ ఎండు పండ్లు','250 g',290),('Dried Cranberries','ఎండిన క్రాన్‌బెర్రీలు','200 g',280),('Prunes','ఎండిన ప్లమ్ పండ్లు','250 g',300),('Makhana','తామర గింజలు (మఖానా)','100 g',160),('Dry Coconut','ఎండు కొబ్బరి','250 g',100),('Pecan Nuts','పెకాన్ గింజలు','200 g',650)]),
('Herbs & powders','మూలికలు & చూర్ణాలు','herbs',[
('Ashwagandha Powder','అశ్వగంధ చూర్ణం','100 g',180),('Triphala Powder','త్రిఫల చూర్ణం','100 g',120),('Amla Powder','ఉసిరి పొడి','100 g',110),('Tulsi Powder','తులసి పొడి','100 g',120),('Neem Leaf Powder','వేపాకు పొడి','100 g',90),('Moringa Leaf Powder','మునగాకు పొడి','100 g',150),('Brahmi Powder','బ్రాహ్మి చూర్ణం','100 g',160),('Shatavari Powder','శతావరి చూర్ణం','100 g',180),('Licorice Powder','అతిమధురం చూర్ణం','100 g',150),('Guduchi Powder','తిప్పతీగ చూర్ణం','100 g',130),('Haritaki Powder','కరక్కాయ చూర్ణం','100 g',100),('Bibhitaki Powder','తానికాయ చూర్ణం','100 g',100),('Arjuna Bark Powder','తెల్ల మద్ది బెరడు చూర్ణం','100 g',130),('Bhringraj Powder','గుంటగలగరాకు పొడి','100 g',130),('Hibiscus Powder','మందార పూల పొడి','100 g',130),('Rose Petal Powder','గులాబీ రేకుల పొడి','100 g',160),('Orange Peel Powder','నారింజ తొక్కల పొడి','100 g',100),('Sandalwood Powder','గంధపు పొడి','25 g',250),('Vetiver Roots','వట్టి వేళ్లు','50 g',110),('Avaram Flower Powder','తంగేడు పూల పొడి','100 g',140),('Manjistha Powder','మంజిష్ఠ చూర్ణం','100 g',190),('Punarnava Powder','పునర్నవ చూర్ణం','100 g',150),('Gokshura Powder','పల్లేరు చూర్ణం','100 g',150),('Bael Fruit Powder','మారేడు పండ్ల పొడి','100 g',130),('Jamun Seed Powder','నేరేడు గింజల పొడి','100 g',140),('Wheatgrass Powder','గోధుమ గడ్డి పొడి','100 g',190),('Curry Leaf Powder','కరివేపాకు పొడి','100 g',100),('Mint Leaf Powder','పుదీనా ఆకుల పొడి','100 g',110),('Lemongrass','నిమ్మగడ్డి','50 g',100),('Dried Tulsi Leaves','ఎండిన తులసి ఆకులు','50 g',90),('Dried Amla','ఎండిన ఉసిరికాయలు','100 g',120),('Haritaki Whole','కరక్కాయలు','100 g',100),('Soapnuts','కుంకుడుకాయలు','250 g',100),('Shikakai','శీకాకాయ','250 g',130)]),
('Seeds & superfoods','విత్తనాలు & పోషకాహారం','seeds',[
('Pumpkin Seeds','గుమ్మడి గింజలు','250 g',220),('Sunflower Seeds','పొద్దుతిరుగుడు గింజలు','250 g',160),('Flax Seeds','అవిసె గింజలు','250 g',100),('Chia Seeds','చియా విత్తనాలు','250 g',180),('Basil Seeds','సబ్జా గింజలు','100 g',90),('Watermelon Seeds','పుచ్చకాయ గింజలు','250 g',240),('White Sesame','తెల్ల నువ్వులు','250 g',110),('Black Sesame','నల్ల నువ్వులు','250 g',120),('Garden Cress Seeds','హలీమ్ గింజలు','100 g',100),('Mixed Seeds','మిశ్రమ గింజలు','250 g',210),('Quinoa','క్వినోవా','500 g',220),('Amaranth Seeds','రాజ్‌గిరా గింజలు','250 g',90)]),
('Oils & natural care','నూనెలు & సహజ సంరక్షణ','care',[
('Almond Oil','బాదం నూనె','100 ml',425),('Cold Pressed Coconut Oil','చెక్క గానుగ కొబ్బరి నూనె','250 ml',220),('Cold Pressed Sesame Oil','చెక్క గానుగ నువ్వుల నూనె','250 ml',180),('Castor Oil','ఆముదం నూనె','100 ml',100),('Neem Oil','వేప నూనె','100 ml',120),('Bhringraj Hair Oil','భృంగరాజ్ కేశ తైలం','100 ml',180),('Amla Hair Oil','ఉసిరి కేశ తైలం','100 ml',130),('Herbal Hair Wash Powder','మూలికల తలస్నానపు పొడి','100 g',120),('Henna Powder','గోరింటాకు పొడి','100 g',90),('Indigo Powder','నీలి ఆకుల పొడి','100 g',150),('Aloe Vera Gel','కలబంద జెల్','100 g',120),('Rose Water','గులాబీ జలం','100 ml',80),('Multani Mitti','ముల్తానీ మట్టి','100 g',70),('Herbal Bath Powder','సున్నిపిండి','200 g',130),('Neem Soap','వేప సబ్బు','75 g',60),('Sandal Soap','గంధపు సబ్బు','75 g',80),('Tulsi Soap','తులసి సబ్బు','75 g',65),('Herbal Toothpaste','మూలికల దంతమంజనం','100 g',95)]),
('Ayurvedic essentials','ఆయుర్వేద ఉత్పత్తులు','ayurveda',[
('Himalaya Ashwagandha','హిమాలయ అశ్వగంధ','60 tablets',260),('Himalaya Triphala','హిమాలయ త్రిఫల','60 tablets',300),('Himalaya Tulasi','హిమాలయ తులసి','60 tablets',260),('Himalaya Brahmi','హిమాలయ బ్రాహ్మి','60 tablets',260),('Himalaya Guduchi','హిమాలయ గుడూచి','60 tablets',260),('Himalaya Arjuna','హిమాలయ అర్జున','60 tablets',325),('Himalaya Gokshura','హిమాలయ గోక్షుర','60 tablets',275),('Himalaya Amalaki','హిమాలయ ఆమలకి','60 tablets',260),('Chyawanprash','చ్యవనప్రాశ','500 g',250),('Amla Juice','ఉసిరి రసం','500 ml',180),('Aloe Vera Juice','కలబంద రసం','500 ml',180),('Herbal Honey','తేనె','250 g',180),('Gulkand','గుల్కంద్','250 g',180),('Amla Candy','ఉసిరి మిఠాయి','200 g',110),('Herbal Tea','మూలికల టీ','100 g',180),('Tulsi Green Tea','తులసి గ్రీన్ టీ','25 bags',170)]),
('Spices & pantry','సుగంధ ద్రవ్యాలు','pantry',[
('Turmeric Powder','పసుపు పొడి','100 g',60),('Dry Ginger','శొంఠి','100 g',100),('Black Pepper','మిరియాలు','100 g',110),('Cinnamon','దాల్చిన చెక్క','50 g',70),('Cloves','లవంగాలు','50 g',90),('Green Cardamom','యాలకులు','50 g',190),('Cumin Seeds','జీలకర్ర','100 g',65),('Fennel Seeds','సోంపు','100 g',60),('Carom Seeds','వాము','100 g',65),('Fenugreek Seeds','మెంతులు','100 g',35),('Coriander Seeds','ధనియాలు','100 g',35),('Nutmeg','జాజికాయ','25 g',65),('Star Anise','అనాస పువ్వు','25 g',60),('Bay Leaves','బిర్యానీ ఆకులు','25 g',35),('Rock Salt','సైంధవ లవణం','500 g',60),('Palm Jaggery','తాటి బెల్లం','500 g',180)])]

class Command(BaseCommand):
    help='Seed an editable, unverified research assortment without overwriting owner changes.'
    def handle(self,*args,**opts):
        count=0
        for en,te,slug,rows in GROUPS:
            category,_=Category.objects.get_or_create(slug=slug,defaults={'name':en,'name_te':te})
            for index,(name,name_te,pack,price) in enumerate(rows):
                sku=f'{slug.upper()}-{index+1:03}'
                if Variant.objects.filter(sku=sku).exists(): continue
                brand='Himalaya' if name.startswith('Himalaya') else ''
                source='https://himalayawellness.in/collections/pure-herbs' if brand else ''
                note='Candidate product. Pack, price, Telugu name and stock need merchant review. Planning estimate, not a store quote.'
                if name=='California Almonds': source='https://business.bigbasket.com/pc/foodgrains-oil-masala/dry-fruits/almonds/'
                if name=='Whole Cashews': source='https://www.bigbasket.com/pd/10000552/bb-royal-cashewkaju-whole-500-g/'
                if name=='Golden Raisins': source='https://www.bigbasket.com/pd/40046740/bb-royal-raisinskishmish-indian-500-g/'
                p=Product.objects.create(category=category,name=name,name_te=name_te,brand=brand,description=f'{name}, {pack}. Review the pack label for ingredients, storage instructions and expiry. Availability is subject to store confirmation.',description_te=f'{name_te}, {pack}. పదార్థాలు, నిల్వ సూచనలు మరియు గడువు తేదీ కోసం ప్యాక్ లేబుల్ చూడండి.',source_url=source,source_note=note,featured=slug=='dry-fruits' and index<6)
                Variant.objects.create(product=p,sku=sku,label=pack,price=price,stock=0)
                count+=1
        store=StoreSettings.get()
        if not store.open_days: store.open_days=[0,1,2,3,4,5];store.save()
        self.stdout.write(f'Added {count} candidate products. All are unverified with zero stock; checkout remains closed.')
